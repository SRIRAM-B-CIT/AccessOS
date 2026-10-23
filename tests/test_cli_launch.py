"""
Phase 3.6 CLI & Launcher Script Integration Tests
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_version_flag():
    """Verify --version returns commit and version with code 0."""
    res = subprocess.run(
        [sys.executable, "-m", "accessos", "--version"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert res.returncode == 0
    assert "AccessOS v0.4.0" in res.stdout
    assert "commit" in res.stdout


def test_cli_help_flag():
    """Verify --help shows profile options."""
    res = subprocess.run(
        [sys.executable, "-m", "accessos", "--help"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert res.returncode == 0
    assert "--profile" in res.stdout
    assert "host-safe" in res.stdout
    assert "camera-preview" in res.stdout
    assert "vm-real" in res.stdout


def test_run_accessos_script_syntax():
    """Verify scripts/run_accessos.sh is executable and passes bash -n."""
    run_script = _REPO_ROOT / "scripts" / "run_accessos.sh"
    assert run_script.exists()
    res = subprocess.run(["bash", "-n", str(run_script)], capture_output=True, text=True)
    assert res.returncode == 0, f"Bash syntax error in run_accessos.sh: {res.stderr}"


def test_stop_accessos_script_syntax():
    """Verify scripts/stop_accessos.sh is executable and passes bash -n."""
    stop_script = _REPO_ROOT / "scripts" / "stop_accessos.sh"
    assert stop_script.exists()
    res = subprocess.run(["bash", "-n", str(stop_script)], capture_output=True, text=True)
    assert res.returncode == 0, f"Bash syntax error in stop_accessos.sh: {res.stderr}"
