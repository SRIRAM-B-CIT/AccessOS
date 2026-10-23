"""
AccessOS Head Pointer Engine (Input-Safety Redesign)
=====================================================
Real-time head-pose and nose-tip tracking for hands-free cursor control.
Processes RGB camera frames using MediaPipe FaceLandmarker, maps head
displacement to pointer motion with deadzone filtering, One-Euro
smoothing, and dwell-to-click.

Guarantees (Phase 3.5 Input Safety):
  - Uses DryRunMouseBackend by default for safe bare-metal host development.
  - Zero OS-level synthetic mouse events sent to host window server.
  - Releases all synthetic buttons and resets dwell on Pause, Stop, Tracking Loss,
    Camera Error, Exception, and Emergency Stop.
  - Fails safely with HostSafetyViolationError if real injection is attempted on host.
"""
from __future__ import annotations

import enum
import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from ..settings.camera_detector import CameraDetector
from ..utils.config import Config
from ..utils.environment import HostSafetyViolationError, can_use_real_mouse_injection
from .dwell_clicker import DwellClicker
from .filters import PointFilter2D
from .mouse_backend import (
    BaseMouseBackend,
    DryRunMouseBackend,
)
from .x11_mouse import (
    UnsupportedSessionError,
    check_session_supported,
)

log = logging.getLogger(__name__)

_DEFAULT_MODEL = Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "face_landmarker.task"

# MediaPipe face landmarks
_NOSE_TIP_IDX = 1
_FOREHEAD_IDX = 10
_CHIN_IDX = 152
_LEFT_EAR_IDX = 234
_RIGHT_EAR_IDX = 454


class TrackingState(enum.Enum):
    STOPPED     = "STOPPED"
    CALIBRATING = "CALIBRATING"
    TRACKING    = "TRACKING"
    LOST        = "LOST"
    PAUSED      = "PAUSED"


class HeadPointerEngine:
    """Head pointer tracking engine with modular, host-safe mouse backends."""

    def __init__(
        self,
        config: Config,
        camera_device: str | None = None,
        model_path: Path | None = None,
        mouse_backend: BaseMouseBackend | None = None,
        preview_only: bool = False,
        on_state_changed: Callable[[TrackingState, str], None] | None = None,
        on_metrics_updated: Callable[[float, float], None] | None = None,
        on_dwell_progress: Callable[[float, int, int], None] | None = None,
        on_click: Callable[[int, int], None] | None = None,
    ) -> None:
        self._config = config
        if not camera_device:
            saved_dev = self._config.get("camera", "device", default=None)
            if saved_dev and Path(saved_dev).exists():
                self._camera_device = saved_dev
            else:
                rec = CameraDetector().get_recommended_camera()
                self._camera_device = rec.device_node if rec else "/dev/video2"
        else:
            self._camera_device = camera_device

        self._model_path = Path(model_path or _DEFAULT_MODEL)

        self.preview_only = preview_only

        # In preview_only mode, real injection is strictly blocked and dry-run is forced
        if self.preview_only:
            self._mouse_backend = DryRunMouseBackend()
        else:
            self._mouse_backend = mouse_backend or DryRunMouseBackend()

        self.on_state_changed = on_state_changed
        self.on_metrics_updated = on_metrics_updated
        self.on_dwell_progress = on_dwell_progress
        self.on_click = on_click

        self._state = TrackingState.STOPPED
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self._filter = PointFilter2D(deadzone=0.015, min_cutoff=1.0, beta=0.008)

        # Dwell clicker (disabled in preview_only mode)
        if self.preview_only:
            self._dwell = None
            log.info("HeadPointerEngine in PREVIEW_ONLY mode: DwellClicker disabled, OS input disabled")
        else:
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

        # Performance metrics
        self._fps: float = 0.0
        self._latency_ms: float = 0.0

        log.info(
            "HeadPointerEngine initialized (camera: %s, backend: %s, safe_mode: %s)",
            self._camera_device,
            type(self._mouse_backend).__name__,
            not self._mouse_backend.is_real_injection,
        )

    @property
    def state(self) -> TrackingState:
        return self._state

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    @property
    def mouse_backend(self) -> BaseMouseBackend:
        return self._mouse_backend

    def set_mouse_backend(self, backend: BaseMouseBackend) -> None:
        """Swap pointer backend (e.g. updating screen size or entering VM mode)."""
        if self._mouse_backend:
            self._mouse_backend.release_all_buttons()
        self._mouse_backend = backend

    def _set_state(self, new_state: TrackingState, detail: str = "") -> None:
        self._state = new_state
        log.info("TrackingState -> %s (%s)", new_state.value, detail)
        if self.on_state_changed:
            try:
                self.on_state_changed(new_state, detail)
            except Exception as exc:
                log.error("on_state_changed callback failed: %s", exc)

    def _handle_dwell_progress(self, progress: float, x: int, y: int) -> None:
        if self.on_dwell_progress:
            self.on_dwell_progress(progress, x, y)

    def _handle_dwell_click(self, x: int, y: int) -> None:
        if self._mouse_backend:
            self._mouse_backend.click(1)
        if self.on_click:
            self.on_click(x, y)

    def calibrate(self) -> None:
        """Mark next detected face landmark as center baseline."""
        self._calibrated = False
        log.info("Recalibration requested")

    def pause(self) -> None:
        """Idempotent safety pause: cancels dwell, releases buttons, halts pointer updates."""
        self._pause_event.set()
        if self._dwell: self._dwell.reset()
        if self._mouse_backend:
            self._mouse_backend.release_all_buttons()
        self._set_state(TrackingState.PAUSED, "Pointer paused safely by user")

    def resume(self) -> None:
        """Explicitly resume pointer control after a pause."""
        self._pause_event.clear()
        if self._dwell: self._dwell.reset()
        self._set_state(TrackingState.TRACKING, "Pointer control resumed")

    def emergency_stop(self) -> None:
        """
        Universal Emergency Stop.
        Immediately cancels dwell, releases all synthetic buttons, stops camera and worker.
        """
        log.warning("EMERGENCY STOP triggered on HeadPointerEngine")
        if self._dwell: self._dwell.reset()
        if self._mouse_backend:
            self._mouse_backend.release_all_buttons()
        self.stop()

    def start(self) -> bool:
        """Start tracking worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            log.warning("HeadPointerEngine is already running")
            return True

        if not self._model_path.exists():
            log.error("FaceLandmarker model file not found at: %s", self._model_path)
            self._set_state(TrackingState.STOPPED, "Model file missing")
            return False

        # If real injection was requested, verify permission
        if self._mouse_backend.is_real_injection:
            allowed, reason = can_use_real_mouse_injection()
            if not allowed:
                log.critical("SAFETY VIOLATION PREVENTED: %s", reason)
                self._set_state(TrackingState.STOPPED, reason)
                raise HostSafetyViolationError(reason)

        self._stop_event.clear()
        self._pause_event.clear()
        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="AccessOS-HeadPointer-Worker",
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def stop(self) -> None:
        """Stop tracking worker thread and clean up all resources."""
        self._stop_event.set()
        self._pause_event.clear()
        if self._dwell: self._dwell.reset()
        if self._mouse_backend:
            self._mouse_backend.release_all_buttons()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None
        self._set_state(TrackingState.STOPPED, "Stopped")

    # ── Main Vision Processing Loop ────────────────────────────────────────────

    def _run_loop(self) -> None:
        cap: cv2.VideoCapture | None = None
        detector = None

        try:
            screen_w, screen_h = self._mouse_backend.screen_size
            center_x, center_y = screen_w // 2, screen_h // 2

            # Open verified RGB camera first before allocating heavy neural net pipeline
            num_match = re.search(r"\d+", str(self._camera_device))
            dev_idx = int(num_match.group()) if num_match else 0

            cap = cv2.VideoCapture(dev_idx)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self._camera_device)

            if not cap.isOpened():
                log.error("Could not open camera device: %s", self._camera_device)
                self._set_state(TrackingState.STOPPED, f"Failed to open {self._camera_device}")
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)

            # Initialize MediaPipe FaceLandmarker
            base_options = python.BaseOptions(model_asset_path=str(self._model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
            )
            detector = vision.FaceLandmarker.create_from_options(options)

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
                    log.warning("Camera frame read failed — retrying")
                    time.sleep(0.03)
                    continue

                capture_time = time.monotonic()
                # Mirror horizontally for natural head-tracking interaction
                frame = cv2.flip(frame, 1)

                # Convert BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp_image = python.vision.core.image.Image(
                    image_format=python.vision.core.image.ImageFormat.SRGB,
                    data=rgb_frame,
                )

                # Inference
                results = detector.detect(mp_image)

                if results.face_landmarks and len(results.face_landmarks) > 0:
                    landmarks = results.face_landmarks[0]
                    nose = landmarks[_NOSE_TIP_IDX]

                    cur_x, cur_y = nose.x, nose.y

                    # Calibration check
                    if not self._calibrated:
                        self._calib_x = cur_x
                        self._calib_y = cur_y
                        self._calibrated = True
                        self._filter.reset()
                        log.info("Calibrated head center to (%.3f, %.3f)", self._calib_x, self._calib_y)

                    # Displacement relative to calibrated center
                    dx = cur_x - self._calib_x
                    dy = cur_y - self._calib_y

                    # Sensitivity scaling
                    sens_x = float(self._config.get("accessibility", "sensitivity_x", default=2.2))
                    sens_y = float(self._config.get("accessibility", "sensitivity_y", default=2.2))

                    raw_screen_x = center_x + (dx * sens_x * screen_w)
                    raw_screen_y = center_y + (dy * sens_y * screen_h)

                    # Deadzone and One-Euro filtering
                    smooth_x, smooth_y = self._filter.filter(raw_screen_x, raw_screen_y, capture_time)

                    target_x = max(0, min(screen_w - 1, int(round(smooth_x))))
                    target_y = max(0, min(screen_h - 1, int(round(smooth_y))))

                    # Move cursor via configured backend (DryRun or X11)
                    self._mouse_backend.move_to(target_x, target_y)

                    # Update dwell clicker
                    if self._dwell is not None: self._dwell.update(target_x, target_y, capture_time)

                    if tracking_lost_announced or self._state != TrackingState.TRACKING:
                        tracking_lost_announced = False
                        self._set_state(TrackingState.TRACKING, "Face tracked")

                else:
                    # ── Face Tracking Lost ──
                    if not tracking_lost_announced:
                        tracking_lost_announced = True
                        log.warning("Face tracking lost — pointer frozen safely, buttons released")
                        if self._dwell: self._dwell.reset()
                        if self._mouse_backend:
                            self._mouse_backend.release_all_buttons()
                        self._set_state(TrackingState.LOST, "Tracking lost — keyboard/mouse active")

                # Metrics calculation
                loop_end = time.monotonic()
                latency = (loop_end - loop_start) * 1000.0
                self._latency_ms = round(latency, 1)

                frame_times.append(loop_end)
                cutoff = loop_end - 1.0
                frame_times = [t for t in frame_times if t >= cutoff]
                self._fps = round(float(len(frame_times)), 1)

                if self.on_metrics_updated:
                    try:
                        self.on_metrics_updated(self._fps, self._latency_ms)
                    except Exception:
                        pass

                # Cap at ~30 FPS
                elapsed = loop_end - loop_start
                target_dt = 1.0 / 30.0
                if elapsed < target_dt:
                    time.sleep(target_dt - elapsed)

        except HostSafetyViolationError as exc:
            log.critical("HostSafetyViolation: %s", exc)
            self._set_state(TrackingState.STOPPED, str(exc))
        except UnsupportedSessionError as exc:
            log.error("Unsupported session: %s", exc)
            self._set_state(TrackingState.STOPPED, str(exc))
        except Exception as exc:
            log.error("Exception in HeadPointer worker loop: %s", exc, exc_info=True)
            self._set_state(TrackingState.STOPPED, f"Error: {exc}")
        finally:
            if detector is not None and hasattr(detector, "close"):
                try:
                    detector.close()
                    log.info("FaceLandmarker detector closed cleanly")
                except Exception as exc:
                    log.error("Error closing FaceLandmarker: %s", exc)

            if cap:
                try:
                    cap.release()
                    log.info("Camera capture released successfully")
                except Exception as exc:
                    log.error("Error releasing camera: %s", exc)

            if self._dwell: self._dwell.reset()
            if self._mouse_backend:
                try:
                    self._mouse_backend.release_all_buttons()
                except Exception:
                    pass

            self._set_state(TrackingState.STOPPED, "Cleanly stopped")
