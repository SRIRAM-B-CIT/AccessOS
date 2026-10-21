"""
Tests for Camera Detection (Dynamic Metadata, RGB vs IR Classification)
"""
from pathlib import Path
from accessos.settings.camera_detector import CameraDetector, CameraDevice


def test_mock_camera_classification_with_usb_sysfs(tmp_path):
    v4l = tmp_path / "video4linux"
    v4l.mkdir()

    # Mock video0: SunplusIT IR Camera (USB parent structure)
    v0 = v4l / "video0"
    v0.mkdir()
    (v0 / "name").write_text("Integrated IR Camera: Integrate\n")
    usb_ir = tmp_path / "usb_ir"
    usb_ir.mkdir()
    (usb_ir / "manufacturer").write_text("SunplusIT Inc\n")
    (usb_ir / "product").write_text("Integrated IR Camera\n")
    interface0 = usb_ir / "1-5:1.0"
    interface0.mkdir()
    # Link device -> interface0
    (v0 / "device").symlink_to(interface0)

    # Mock video2: Chicony RGB Camera (USB parent structure)
    v2 = v4l / "video2"
    v2.mkdir()
    (v2 / "name").write_text("Integrated Camera: Integrated C\n")
    usb_rgb = tmp_path / "usb_rgb"
    usb_rgb.mkdir()
    (usb_rgb / "manufacturer").write_text("Chicony Electronics Co.,Ltd.\n")
    (usb_rgb / "product").write_text("Integrated Camera\n")
    interface2 = usb_rgb / "1-8:1.0"
    interface2.mkdir()
    (v2 / "device").symlink_to(interface2)

    detector = CameraDetector(sysfs_dir=v4l)
    cams = detector.detect_cameras()

    assert len(cams) == 2

    # video0: dynamically detected as SunplusIT Inc Integrated IR Camera
    cam0 = [c for c in cams if c.device_node == "/dev/video0"][0]
    assert "SunplusIT" in cam0.name
    assert "IR" in cam0.name
    assert cam0.is_ir is True
    assert cam0.is_rgb is False
    assert cam0.is_recommended is False

    # video2: dynamically detected as Chicony Electronics Co.,Ltd. Integrated Camera
    cam2 = [c for c in cams if c.device_node == "/dev/video2"][0]
    assert "Chicony" in cam2.name
    assert cam2.is_rgb is True
    assert cam2.is_ir is False
    assert cam2.is_recommended is True

    # Recommended selection returns video2
    rec = detector.get_recommended_camera()
    assert rec is not None
    assert rec.device_node == "/dev/video2"
    assert "Chicony" in rec.name


def test_real_hardware_detection():
    detector = CameraDetector()
    cams = detector.detect_cameras()
    if cams:
        rec = detector.get_recommended_camera()
        assert rec is not None
        assert rec.is_rgb is True
        assert rec.is_ir is False
        assert rec.device_node == "/dev/video2"
        assert "Chicony" in rec.name


def test_empty_sysfs_graceful(tmp_path):
    empty_dir = tmp_path / "nonexistent_v4l"
    detector = CameraDetector(sysfs_dir=empty_dir)
    cams = detector.detect_cameras()
    assert cams == []
    assert detector.get_recommended_camera() is None
