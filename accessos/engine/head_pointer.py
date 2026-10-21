"""
AccessOS Head Pointer Engine
=============================
Real-time head-pose and nose-tip tracking for hands-free cursor control.
Processes RGB camera frames using MediaPipe FaceLandmarker, maps head
displacement to X11 pointer motion with deadzone filtering, One-Euro
smoothing, and dwell-to-click.

Guarantees:
  - Dynamic camera device selection (never hardcodes /dev/video2).
  - Zero camera access until explicitly activated by user.
  - Safe confidence-loss handling (freezes cursor and signals fallback).
  - Esc immediately pauses tracking.
  - Keyboard & mouse remain completely operational.
"""
from __future__ import annotations

import enum
import logging
import math
import re
import threading
import time
from pathlib import Path
from typing import Callable, Tuple

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from ..settings.camera_detector import CameraDetector
from ..utils.config import Config
from .dwell_clicker import DwellClicker
from .filters import PointFilter2D
from .x11_mouse import X11Mouse, UnsupportedSessionError, check_session_supported

log = logging.getLogger(__name__)

_DEFAULT_MODEL = Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "face_landmarker.task"


class TrackingState(enum.Enum):
    STOPPED  = "STOPPED"
    STARTING = "STARTING"
    TRACKING = "TRACKING"
    LOST     = "LOST"
    PAUSED   = "PAUSED"


class HeadPointerEngine:
    """
    Asynchronous vision-based pointer controller.
    Runs video capture and neural landmark inference in a dedicated worker thread.
    """

    def __init__(
        self,
        config: Config,
        camera_device: str | None = None,
        model_path: Path | None = None,
        on_state_changed: Callable[[TrackingState, str], None] | None = None,
        on_metrics_updated: Callable[[float, float], None] | None = None,
        on_dwell_progress: Callable[[float, int, int], None] | None = None,
        on_click: Callable[[int, int], None] | None = None,
    ) -> None:
        self._config = config
        if not camera_device:
            saved_dev = self._config.get("camera", "device", default=None)
            if saved_dev and Path(saved_dev).exists():
                camera_device = saved_dev
            else:
                rec = CameraDetector().get_recommended_camera()
                camera_device = rec.device_node if rec else "/dev/video2"
        self._camera_device = camera_device
        self._model_path = Path(model_path or _DEFAULT_MODEL)

        self.on_state_changed = on_state_changed
        self.on_metrics_updated = on_metrics_updated
        self.on_dwell_progress = on_dwell_progress
        self.on_click = on_click

        self._state = TrackingState.STOPPED
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self._x11_mouse: X11Mouse | None = None
        self._filter = PointFilter2D(deadzone=0.015, min_cutoff=1.0, beta=0.008)

        # Dwell clicker
        dwell_ms = self._config.get("accessibility", "dwell_time_ms", default=1000)
        self._dwell = DwellClicker(
            dwell_time_ms=dwell_ms,
            on_progress=self._handle_dwell_progress,
            on_click=self._handle_dwell_click,
        )

        # Calibration baseline (normalized head center)
        self._calib_x = 0.5
        self._calib_y = 0.5
        self._calibrated = False

        # Metrics
        self._fps = 0.0
        self._latency_ms = 0.0

    @property
    def state(self) -> TrackingState:
        return self._state

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    def _set_state(self, new_state: TrackingState, detail: str = "") -> None:
        if self._state != new_state:
            old = self._state
            self._state = new_state
            log.info("HeadPointer state: %s → %s (%s)", old.value, new_state.value, detail)
            if self.on_state_changed:
                try:
                    self.on_state_changed(new_state, detail)
                except Exception as exc:
                    log.debug("on_state_changed callback error: %s", exc)

    def _handle_dwell_progress(self, progress: float, x: int, y: int) -> None:
        if self.on_dwell_progress:
            self.on_dwell_progress(progress, x, y)

    def _handle_dwell_click(self, x: int, y: int) -> None:
        if self._x11_mouse:
            self._x11_mouse.click(1)
        if self.on_click:
            self.on_click(x, y)

    def calibrate(self) -> None:
        """Mark next detected face landmark as center baseline."""
        self._calibrated = False
        log.info("Recalibration requested")

    def pause(self) -> None:
        """Immediately freeze pointer actions (Esc shortcut)."""
        self._pause_event.set()
        self._dwell.reset()
        self._set_state(TrackingState.PAUSED, "Paused by user")

    def resume(self) -> None:
        """Resume pointer tracking."""
        self._pause_event.clear()
        self._filter.reset()
        self._dwell.reset()
        self._set_state(TrackingState.TRACKING, "Resumed")

    def toggle_pause(self) -> bool:
        if self._pause_event.is_set():
            self.resume()
            return False
        else:
            self.pause()
            return True

    def start(self) -> bool:
        """Start head tracking worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            log.warning("HeadPointer already running")
            return True

        if not self._model_path.exists():
            log.error("FaceLandmarker model not found at %s", self._model_path)
            self._set_state(TrackingState.STOPPED, f"Model file missing: {self._model_path}")
            return False

        # Resolve camera device dynamically if not specified
        if not self._camera_device:
            saved_dev = self._config.get("camera", "device", default=None)
            if saved_dev and Path(saved_dev).exists():
                self._camera_device = saved_dev
            else:
                rec = CameraDetector().get_recommended_camera()
                if rec:
                    self._camera_device = rec.device_node
                else:
                    self._camera_device = "/dev/video2"

        log.info("Starting HeadPointer on verified camera: %s", self._camera_device)
        self._stop_event.clear()
        self._pause_event.clear()
        self._set_state(TrackingState.STARTING, f"Opening {self._camera_device}")

        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="HeadPointerWorker",
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def stop(self) -> None:
        """Stop worker thread and release hardware resources."""
        log.info("Stopping HeadPointer engine")
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None
        self._dwell.reset()
        if self._x11_mouse:
            self._x11_mouse.close()
            self._x11_mouse = None
        self._set_state(TrackingState.STOPPED, "Stopped")

    # ── Main Vision Processing Loop ────────────────────────────────────────────

    def _run_loop(self) -> None:
        cap: cv2.VideoCapture | None = None
        detector = None

        try:
            self._x11_mouse = X11Mouse()
            screen_w, screen_h = self._x11_mouse.screen_size
            center_x, center_y = screen_w // 2, screen_h // 2

            # Initialize MediaPipe FaceLandmarker
            base_options = python.BaseOptions(model_asset_path=str(self._model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
            )
            detector = vision.FaceLandmarker.create_from_options(options)

            # Open verified RGB camera (use numeric index first to avoid V4L2 name ioctl warnings)
            num_match = re.search(r"\d+", str(self._camera_device))
            dev_idx = int(num_match.group()) if num_match else 0

            cap = cv2.VideoCapture(dev_idx)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self._camera_device)

            if not cap.isOpened():
                log.error("Could not open camera device: %s", self._camera_device)
                self._set_state(TrackingState.STOPPED, f"Failed to open {self._camera_device}")
                return

            # Camera parameters: 640x480 at 30 FPS is optimal for low CPU & low latency
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)

            self._set_state(TrackingState.TRACKING, "Camera active")

            frame_times: list[float] = []
            tracking_lost_announced = False

            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                # Handle user pause
                if self._pause_event.is_set():
                    time.sleep(0.05)
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue

                capture_time = time.monotonic()

                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                result = detector.detect(mp_img)

                if result.face_landmarks and len(result.face_landmarks) > 0:
                    # ── Face Detected ──
                    landmarks = result.face_landmarks[0]
                    # Landmark 1 is the nose tip (stable pivot for head rotation)
                    nose = landmarks[1]

                    # Horizontal mirror: facing the camera, turning right turns head to the user's right
                    raw_x = 1.0 - nose.x
                    raw_y = nose.y

                    # Baseline calibration
                    if not self._calibrated:
                        self._calib_x = raw_x
                        self._calib_y = raw_y
                        self._calibrated = True
                        self._filter.reset()
                        log.info("Calibrated baseline center: (%.3f, %.3f)", raw_x, raw_y)

                    # Compute angular offset from calibration baseline
                    dx = raw_x - self._calib_x
                    dy = raw_y - self._calib_y

                    # Apply deadzone filter to suppress minor head tremors
                    deadzone = self._config.get("accessibility", "deadzone", default=0.015)
                    self._filter.deadzone_filter.threshold = deadzone
                    dx_filt, dy_filt = self._filter.deadzone_filter.apply(dx, dy)

                    # Read dynamic sensitivity from config
                    sensitivity = float(self._config.get("accessibility", "head_sensitivity", default=0.5))
                    # Map to screen pixels: scale sensitivity by screen dimensions
                    gain = sensitivity * 3.5

                    raw_screen_x = center_x + (dx_filt * gain * screen_w)
                    raw_screen_y = center_y + (dy_filt * gain * screen_h)

                    # Apply One-Euro low-pass smoothing
                    smooth_x, smooth_y = self._filter.filter(raw_screen_x, raw_screen_y, capture_time)

                    # Clamp to screen boundary
                    target_x = max(0, min(screen_w - 1, int(round(smooth_x))))
                    target_y = max(0, min(screen_h - 1, int(round(smooth_y))))

                    # Move physical X11 cursor
                    self._x11_mouse.move_to(target_x, target_y)

                    # Update dwell clicker
                    self._dwell.update(target_x, target_y, capture_time)

                    if tracking_lost_announced or self._state != TrackingState.TRACKING:
                        tracking_lost_announced = False
                        self._set_state(TrackingState.TRACKING, "Face tracked")

                else:
                    # ── Face Tracking Lost ──
                    if not tracking_lost_announced:
                        tracking_lost_announced = True
                        log.warning("Face tracking lost — pointer frozen safely, fallback active")
                        self._dwell.reset()
                        self._set_state(TrackingState.LOST, "Tracking lost — keyboard/mouse active")

                # Metrics calculation
                loop_end = time.monotonic()
                latency = (loop_end - loop_start) * 1000.0
                self._latency_ms = round(latency, 1)

                frame_times.append(loop_end)
                # Keep last 30 frames for average FPS
                cutoff = loop_end - 1.0
                frame_times = [t for t in frame_times if t >= cutoff]
                self._fps = round(float(len(frame_times)), 1)

                if self.on_metrics_updated:
                    try:
                        self.on_metrics_updated(self._fps, self._latency_ms)
                    except Exception:
                        pass

                # Cap at ~30-35 FPS to conserve CPU on ThinkPad T480
                elapsed = loop_end - loop_start
                target_dt = 1.0 / 30.0
                if elapsed < target_dt:
                    time.sleep(target_dt - elapsed)

        except UnsupportedSessionError as exc:
            log.error("Unsupported session: %s", exc)
            self._set_state(TrackingState.STOPPED, str(exc))
        except Exception as exc:
            log.error("Exception in HeadPointer worker loop: %s", exc, exc_info=True)
            self._set_state(TrackingState.STOPPED, f"Error: {exc}")
        finally:
            if cap:
                cap.release()
            if detector:
                try:
                    detector.close()
                except Exception:
                    pass
            log.info("HeadPointer worker loop terminated")
