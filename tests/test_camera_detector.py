"""
Tests for Camera Detection (RGB vs IR Classification)
"""
from pathlib import Path
from accessos.settings.camera_detector import CameraDetector, CameraDevice


def test_mock_camera_classification(tmp_path):
    # Setup mock sysfs directory
    v4l = tmp_path / "video4linux"
    v4l.mkdir()

    # Mock video0: Realtek IR Camera
    v0 = v4l / "video0"
    v0.mkdir()
    (v0 / "name").write_text("Integrated IR Camera: Realtek IR\n")

    # Mock video1: Realtek IR stream node
    v1 = v4l / "video1"
    v1.mkdir()
    (v1 / "name").write_text("Integrated IR Camera: Realtek IR\n")

    # Mock video2: SunplusIT RGB Webcam
    v2 = v4l / "video2"
    v2.mkdir()
    (v2 / "name").write_text("Integrated Camera: SunplusIT RGB\n")

    # Mock video3: SunplusIT stream node
    v3 = v4l / "video3"
    v3.mkdir()
    (v3 / "name").write_text("Integrated Camera: SunplusIT RGB\n")

    detector = CameraDetector(sysfs_dir=v4l)
    cams = detector.detect_cameras()

    assert len(cams) == 4

    # video0 must be detected as IR, not recommended
    cam0 = [c for c in cams if c.device_node == "/dev/video0"][0]
    assert cam0.is_ir is True
    assert cam0.is_rgb is False
    assert cam0.is_recommended is False

    # video2 must be detected as RGB and recommended!
    cam2 = [c for c in cams if c.device_node == "/dev/video2"][0]
    assert cam2.is_rgb is True
    assert cam2.is_ir is False
    assert cam2.is_recommended is True

    # Recommended selection returns video2
    rec = detector.get_recommended_camera()
    assert rec is not None
    assert rec.device_node == "/dev/video2"


def test_empty_sysfs_graceful(tmp_path):
    empty_dir = tmp_path / "nonexistent_v4l"
    detector = CameraDetector(sysfs_dir=empty_dir)
    cams = detector.detect_cameras()
    assert cams == []
    assert detector.get_recommended_camera() is None
