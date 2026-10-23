"""
Phase 3.6 Launch Profiles & Prerequisite Enforcement Tests
"""
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from accessos.utils.profile import (
    LaunchProfile,
    resolve_profile,
    validate_profile_prerequisites,
)
from accessos.utils.environment import HostSafetyViolationError
from accessos.home_screen import HomeScreen


def test_resolve_profile_defaults_to_host_safe():
    with patch.dict(os.environ, {}, clear=True):
        p = resolve_profile(None)
        assert p == LaunchProfile.HOST_SAFE


def test_resolve_profile_cli_argument():
    assert resolve_profile("camera-preview") == LaunchProfile.CAMERA_PREVIEW
    assert resolve_profile("host-safe") == LaunchProfile.HOST_SAFE
    assert resolve_profile("vm-real") == LaunchProfile.VM_REAL


def test_resolve_profile_environment_variable():
    with patch.dict(os.environ, {"ACCESSOS_PROFILE": "camera-preview"}):
        assert resolve_profile(None) == LaunchProfile.CAMERA_PREVIEW


def test_resolve_profile_invalid_raises_value_error():
    with pytest.raises(ValueError) as exc:
        resolve_profile("invalid-profile")
    assert "Unknown launch profile" in str(exc.value)


def test_validate_profile_host_safe_and_preview_pass_on_host():
    validate_profile_prerequisites(LaunchProfile.HOST_SAFE)
    validate_profile_prerequisites(LaunchProfile.CAMERA_PREVIEW)


def test_validate_profile_vm_real_fails_on_host():
    with patch("accessos.utils.environment.is_running_in_vm", return_value=(False, "Bare Metal Host")):
        with pytest.raises(HostSafetyViolationError) as exc:
            validate_profile_prerequisites(LaunchProfile.VM_REAL)
        assert "VM_REAL profile cannot be activated" in str(exc.value)


def test_validate_profile_vm_real_requires_vm_config_file():
    with patch("accessos.utils.environment.is_running_in_vm", return_value=(True, "VirtualBox")):
        non_existent_config = Path("/tmp/does_not_exist_vm_config.toml")
        with pytest.raises(HostSafetyViolationError) as exc:
            validate_profile_prerequisites(LaunchProfile.VM_REAL, vm_config_path=non_existent_config)
        assert "Missing VM configuration file" in str(exc.value)


def test_host_safe_profile_initializes_no_engine_and_no_mouse_backend():
    """Host safe mode must start ONLY the UI with zero engine and zero mouse backend."""
    win = HomeScreen(profile=LaunchProfile.HOST_SAFE)
    assert win._profile == LaunchProfile.HOST_SAFE
    assert win._engine is None
    assert win._mouse_backend is None
    assert "HOST SAFE" in win._safety_badge.get_label()
    win.destroy()


def test_camera_preview_profile_initializes_no_dwell_and_dry_run_only():
    """Camera preview mode must NOT initialize dwell clicking or any OS input backend."""
    win = HomeScreen(profile=LaunchProfile.CAMERA_PREVIEW)
    assert win._profile == LaunchProfile.CAMERA_PREVIEW
    assert win._engine is not None
    assert win._engine.preview_only is True
    # Invariant: Dwell clicker is strictly None
    assert win._engine._dwell is None
    # Invariant: Mouse backend is strictly virtual dry-run
    assert win._mouse_backend.is_real_injection is False
    assert "CAMERA PREVIEW" in win._safety_badge.get_label()
    win.destroy()
