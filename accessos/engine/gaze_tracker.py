"""
AccessOS Experimental Eye-Gaze Tracking Engine
===============================================
Estimates gaze fixation and screen focus from normalized pupil/iris displacements
relative to eye corners using MediaPipe FaceLandmarker.

Features & Invariants:
  - 5-point guided calibration procedure (Center, Top-Left, Top-Right, Bottom-Left, Bottom-Right).
  - Temporal smoothing via One-Euro filter and deadzone stabilization.
  - Confidence metric based on eye aspect ratio and face alignment.
  - Honest accuracy limitations notice for standard 720p webcams.
  - In host testing: renders virtual reticle inside AccessOS window only; never creates real host clicks.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .filters import PointFilter2D

log = logging.getLogger(__name__)

# Landmark indices for Iris and Eye Bounding Geometry
# Left Eye & Iris
_L_IRIS_CENTER  = 468
_L_CORNER_INNER = 133
_L_CORNER_OUTER = 33
_L_LID_UPPER    = 159
_L_LID_LOWER    = 145

# Right Eye & Iris
_R_IRIS_CENTER  = 473
_R_CORNER_INNER = 362
_R_CORNER_OUTER = 263
_R_LID_UPPER    = 386
_R_LID_LOWER    = 374

_ACCURACY_DISCLAIMER = (
    "Eye gaze on standard integrated 720p webcams without active infrared illumination "
    "is experimental. Accuracy is approximate (~100–150px) and sensitive to ambient lighting. "
    "Recommended for coarse selection; combine with dwell or head pointer for precision."
)


@dataclass
class GazeSample:
    pupil_x: float
    pupil_y: float
    confidence: float


@dataclass
class GazeTarget:
    name: str
    norm_x: float  # Normalized screen target [0.0 .. 1.0]
    norm_y: float


CALIBRATION_TARGETS: List[GazeTarget] = [
    GazeTarget("Center", 0.50, 0.50),
    GazeTarget("Top-Left", 0.15, 0.15),
    GazeTarget("Top-Right", 0.85, 0.15),
    GazeTarget("Bottom-Left", 0.15, 0.85),
    GazeTarget("Bottom-Right", 0.85, 0.85),
]


class GazeTracker:
    """Experimental 2D eye-gaze tracking and calibration engine."""

    def __init__(
        self,
        screen_size: Tuple[int, int] = (1280, 720),
        on_calibration_progress: Optional[Callable[[int, int, str], None]] = None,
        on_calibration_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        self.screen_w, self.screen_h = screen_size
        self.on_calibration_progress = on_calibration_progress
        self.on_calibration_complete = on_calibration_complete

        self._filter = PointFilter2D(deadzone=0.02, min_cutoff=0.8, beta=0.012)
        self.accuracy_warning: str = _ACCURACY_DISCLAIMER

        # Calibration state
        self.is_calibrating: bool = False
        self.is_calibrated: bool = False
        self._calib_target_idx: int = 0
        self._target_samples: Dict[str, List[Tuple[float, float]]] = {}

        # Default transformation mapping (pupil ratio to screen coordinates)
        # Normal relaxed forward gaze sits around (0.5, 0.5)
        self._scale_x: float = 3.2
        self._scale_y: float = 4.0
        self._offset_x: float = 0.5
        self._offset_y: float = 0.5

    def set_screen_size(self, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self.screen_w = width
            self.screen_h = height

    def start_calibration(self) -> None:
        """Begin guided 5-point gaze calibration."""
        log.info("Starting guided 5-point eye gaze calibration")
        self.is_calibrating = True
        self.is_calibrated = False
        self._calib_target_idx = 0
        self._target_samples = {t.name: [] for t in CALIBRATION_TARGETS}
        self._announce_current_target()

    def cancel_calibration(self) -> None:
        self.is_calibrating = False
        self._calib_target_idx = 0
        log.info("Gaze calibration canceled")

    def _announce_current_target(self) -> None:
        if self._calib_target_idx < len(CALIBRATION_TARGETS):
            target = CALIBRATION_TARGETS[self._calib_target_idx]
            log.info("Calibration target [%d/%d]: %s (%.2f, %.2f)",
                     self._calib_target_idx + 1, len(CALIBRATION_TARGETS), target.name, target.norm_x, target.norm_y)
            if self.on_calibration_progress:
                try:
                    self.on_calibration_progress(
                        self._calib_target_idx + 1,
                        len(CALIBRATION_TARGETS),
                        target.name,
                    )
                except Exception as exc:
                    log.error("on_calibration_progress error: %s", exc)

    def extract_pupil_ratio(self, landmarks: List[Any]) -> Optional[GazeSample]:
        """
        Extract normalized horizontal and vertical pupil position within the eye sockets.
        Returns GazeSample with normalized coordinates centered at ~0.5.
        """
        if len(landmarks) < 478:
            return None

        try:
            # Left Eye: Iris vs Corners
            l_iris = landmarks[_L_IRIS_CENTER]
            l_inner = landmarks[_L_CORNER_INNER]
            l_outer = landmarks[_L_CORNER_OUTER]
            l_upper = landmarks[_L_LID_UPPER]
            l_lower = landmarks[_L_LID_LOWER]

            l_eye_w = abs(l_inner.x - l_outer.x)
            l_eye_h = abs(l_lower.y - l_upper.y)

            if l_eye_w < 1e-4 or l_eye_h < 1e-4:
                return None

            l_rx = (l_iris.x - min(l_inner.x, l_outer.x)) / l_eye_w
            l_ry = (l_iris.y - min(l_upper.y, l_lower.y)) / l_eye_h

            # Right Eye: Iris vs Corners
            r_iris = landmarks[_R_IRIS_CENTER]
            r_inner = landmarks[_R_CORNER_INNER]
            r_outer = landmarks[_R_CORNER_OUTER]
            r_upper = landmarks[_R_LID_UPPER]
            r_lower = landmarks[_R_LID_LOWER]

            r_eye_w = abs(r_inner.x - r_outer.x)
            r_eye_h = abs(r_lower.y - r_upper.y)

            if r_eye_w < 1e-4 or r_eye_h < 1e-4:
                return None

            r_rx = (r_iris.x - min(r_inner.x, r_outer.x)) / r_eye_w
            r_ry = (r_iris.y - min(r_upper.y, r_lower.y)) / r_eye_h

            # Average pupil ratios
            pupil_x = (l_rx + r_rx) / 2.0
            pupil_y = (l_ry + r_ry) / 2.0

            # Confidence based on eye openness
            confidence = min(1.0, max(0.0, ((l_eye_h / l_eye_w) + (r_eye_h / r_eye_w)) * 2.5))

            return GazeSample(pupil_x=pupil_x, pupil_y=pupil_y, confidence=confidence)
        except Exception as exc:
            log.debug("Error extracting pupil ratio: %s", exc)
            return None

    def record_calibration_sample(self, landmarks: List[Any]) -> bool:
        """
        Record gaze sample for the active calibration target.
        Returns True when all 5 points have completed calibration.
        """
        if not self.is_calibrating:
            return False

        sample = self.extract_pupil_ratio(landmarks)
        if not sample or sample.confidence < 0.3:
            return False

        target = CALIBRATION_TARGETS[self._calib_target_idx]
        self._target_samples[target.name].append((sample.pupil_x, sample.pupil_y))

        # Collect 20 valid samples per target (~0.7s at 30 FPS)
        if len(self._target_samples[target.name]) >= 20:
            self._calib_target_idx += 1
            if self._calib_target_idx >= len(CALIBRATION_TARGETS):
                self._compute_calibration_model()
                self.is_calibrating = False
                self.is_calibrated = True
                log.info("5-Point gaze calibration completed successfully!")
                if self.on_calibration_complete:
                    try:
                        self.on_calibration_complete()
                    except Exception as exc:
                        log.error("on_calibration_complete error: %s", exc)
                return True
            else:
                self._announce_current_target()

        return False

    def _compute_calibration_model(self) -> None:
        """Compute scale and offset mapping from collected calibration points."""
        try:
            # Average baseline pupil for each target
            avg_pts = {}
            for name, pts in self._target_samples.items():
                if pts:
                    avg_x = sum(p[0] for p in pts) / len(pts)
                    avg_y = sum(p[1] for p in pts) / len(pts)
                    avg_pts[name] = (avg_x, avg_y)

            if "Center" in avg_pts:
                self._offset_x = avg_pts["Center"][0]
                self._offset_y = avg_pts["Center"][1]

            # Horizontal span between left and right calibration targets
            left_x = (avg_pts.get("Top-Left", (0.4, 0.5))[0] + avg_pts.get("Bottom-Left", (0.4, 0.5))[0]) / 2.0
            right_x = (avg_pts.get("Top-Right", (0.6, 0.5))[0] + avg_pts.get("Bottom-Right", (0.6, 0.5))[0]) / 2.0
            span_x = abs(right_x - left_x)
            if span_x > 0.02:
                # 0.70 normalized screen distance between 0.15 and 0.85
                self._scale_x = 0.70 / span_x

            # Vertical span between top and bottom calibration targets
            top_y = (avg_pts.get("Top-Left", (0.5, 0.4))[1] + avg_pts.get("Top-Right", (0.5, 0.4))[1]) / 2.0
            bottom_y = (avg_pts.get("Bottom-Left", (0.5, 0.6))[1] + avg_pts.get("Bottom-Right", (0.5, 0.6))[1]) / 2.0
            span_y = abs(bottom_y - top_y)
            if span_y > 0.02:
                self._scale_y = 0.70 / span_y

            log.info("Gaze Calibration Model: Center=(%.3f, %.3f), Scale=(%.2f, %.2f)",
                     self._offset_x, self._offset_y, self._scale_x, self._scale_y)
        except Exception as exc:
            log.warning("Calibration math error, falling back to defaults: %s", exc)

    def estimate_gaze(self, landmarks: List[Any], timestamp: Optional[float] = None) -> Optional[Tuple[int, int, float]]:
        """
        Estimate screen coordinates (x, y) and confidence from facial landmarks.
        Returns: (screen_x, screen_y, confidence) or None if eyes not tracked.
        """
        sample = self.extract_pupil_ratio(landmarks)
        if not sample:
            return None

        # Pupil displacement relative to calibrated center
        dx = (sample.pupil_x - self._offset_x) * self._scale_x
        dy = (sample.pupil_y - self._offset_y) * self._scale_y

        center_screen_x = self.screen_w / 2.0
        center_screen_y = self.screen_h / 2.0

        raw_x = center_screen_x + (dx * self.screen_w)
        raw_y = center_screen_y + (dy * self.screen_h)

        # Apply deadzone and One-Euro smoothing filter
        t = time.monotonic() if timestamp is None else timestamp
        smooth_x, smooth_y = self._filter.filter(raw_x, raw_y, t)

        target_x = max(0, min(self.screen_w - 1, int(round(smooth_x))))
        target_y = max(0, min(self.screen_h - 1, int(round(smooth_y))))

        return target_x, target_y, sample.confidence
