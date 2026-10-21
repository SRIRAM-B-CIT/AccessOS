"""
AccessOS Camera Hardware Detector
===================================
Discovers and classifies video input devices on the system via sysfs.
Distinguishes RGB webcams from Infrared (IR) sensors without opening
video streams or requesting camera frames (Phase 2 compliance).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_SYSFS_V4L = Path("/sys/class/video4linux")


@dataclass
class CameraDevice:
    device_node: str       # e.g. "/dev/video2"
    sys_name: str          # e.g. "video2"
    name: str              # e.g. "Integrated Camera: Integrated C"
    is_rgb: bool           # True if standard color camera
    is_ir: bool            # True if infrared camera (e.g. Realtek IR)
    is_recommended: bool   # True if best candidate for computer vision
    description: str       # User-friendly explanation


class CameraDetector:
    """
    Scans Video4Linux devices in sysfs and identifies the best RGB webcam.
    Does NOT invoke cv2.VideoCapture or open device file descriptors.
    """

    def __init__(self, sysfs_dir: Path | None = None) -> None:
        self.sysfs_dir = sysfs_dir or _SYSFS_V4L

    def detect_cameras(self) -> list[CameraDevice]:
        devices: list[CameraDevice] = []
        if not self.sysfs_dir.exists():
            log.warning("V4L sysfs directory not found: %s", self.sysfs_dir)
            return devices

        # Sort video nodes numerically (video0, video1, video2, etc.)
        def _sort_key(p: Path) -> int:
            m = re.search(r"\d+", p.name)
            return int(m.group()) if m else 999

        entries = sorted(
            [p for p in self.sysfs_dir.iterdir() if p.name.startswith("video")],
            key=_sort_key,
        )

        recommended_found = False

        for entry in entries:
            name_file = entry / "name"
            if not name_file.exists():
                continue

            try:
                raw_name = name_file.read_text(encoding="utf-8").strip()
            except Exception as exc:
                log.debug("Could not read name from %s: %s", name_file, exc)
                continue

            sys_name = entry.name
            dev_node = f"/dev/{sys_name}"

            # Classify RGB vs IR
            is_ir = "ir" in raw_name.lower() or "infrared" in raw_name.lower()
            is_rgb = not is_ir

            # In Linux V4L2, each USB/integrated camera often exposes two nodes:
            # videoN (primary capture) and videoN+1 (metadata/stream info).
            # Even-numbered nodes or nodes with capture capability are typically primary.
            num_match = re.search(r"\d+", sys_name)
            num = int(num_match.group()) if num_match else 0
            is_metadata_node = (num % 2 == 1)

            # Mark recommended RGB camera
            is_rec = False
            if is_rgb and not is_metadata_node and not recommended_found:
                is_rec = True
                recommended_found = True

            if is_ir:
                desc = f"Infrared Sensor ({raw_name}) — Not suitable for RGB color tracking"
            elif is_rec:
                desc = f"RGB Webcam ({raw_name}) — Recommended for head/eye tracking"
            elif is_metadata_node:
                desc = f"Metadata/Stream stream node for camera ({raw_name})"
            else:
                desc = f"RGB Video Device ({raw_name})"

            devices.append(
                CameraDevice(
                    device_node=dev_node,
                    sys_name=sys_name,
                    name=raw_name,
                    is_rgb=is_rgb,
                    is_ir=is_ir,
                    is_recommended=is_rec,
                    description=desc,
                )
            )

        log.info("Detected %d camera devices (%s)", len(devices), [d.device_node for d in devices])
        return devices

    def get_recommended_camera(self) -> CameraDevice | None:
        cameras = self.detect_cameras()
        for cam in cameras:
            if cam.is_recommended:
                return cam
        # Fallback to any RGB camera
        for cam in cameras:
            if cam.is_rgb and not cam.is_ir:
                return cam
        return cameras[0] if cameras else None
