"""
Phase 3.6 Static and Runtime Safety Audit Test Suite
=====================================================
Enforces the Phase 3.6 Input-Safety Invariants:
1. Static AST analysis: host-safe modules must NOT import ctypes, X11MouseBackend,
   libXtst, XTest, xdotool, pyautogui, pynput, or any global input API.
2. Host mouse_backend.py must never import ctypes or native injection libraries.
3. DryRunMouseBackend operates purely in-memory with is_real_injection=False.
"""
import ast
import os
import sys
from pathlib import Path
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ACCESSOS_DIR = _REPO_ROOT / "accessos"

# Files that run on bare-metal host systems during host-safe development
_HOST_SAFE_FILES = [
    _ACCESSOS_DIR / "home_screen.py",
    _ACCESSOS_DIR / "engine" / "mouse_backend.py",
    _ACCESSOS_DIR / "engine" / "head_pointer.py",
    _ACCESSOS_DIR / "engine" / "dwell_clicker.py",
    _ACCESSOS_DIR / "engine" / "virtual_cursor.py",
    _ACCESSOS_DIR / "engine" / "filters.py",
    _ACCESSOS_DIR / "utils" / "environment.py",
    _ACCESSOS_DIR / "utils" / "profile.py",
    _ACCESSOS_DIR / "utils" / "instance_lock.py",
    _ACCESSOS_DIR / "utils" / "build_info.py",
    _ACCESSOS_DIR / "app_launcher.py",
    _ACCESSOS_DIR / "audio_feedback.py",
    _ACCESSOS_DIR / "status_bar.py",
]

_FORBIDDEN_MODULES = {
    "ctypes",
    "ctypes.util",
    "xdotool",
    "pyautogui",
    "pynput",
    "uinput",
    "evdev",
}


def _get_module_imports(filepath: Path) -> set[str]:
    """Parse AST of a Python file and collect all top-level imported module names."""
    tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_host_safe_modules_contain_no_forbidden_input_libraries():
    """Verify that zero host-safe modules import ctypes, pyautogui, xdotool, etc."""
    violations = []
    for filepath in _HOST_SAFE_FILES:
        assert filepath.exists(), f"Host safe file {filepath} not found"
        imported_modules = _get_module_imports(filepath)
        found_forbidden = imported_modules.intersection(_FORBIDDEN_MODULES)
        if found_forbidden:
            violations.append(f"{filepath.name} imports forbidden: {found_forbidden}")

    assert not violations, "Host safety violation in AST analysis:\n" + "\n".join(violations)


def test_mouse_backend_has_no_ctypes():
    """Explicitly verify accessos/engine/mouse_backend.py has zero ctypes imports."""
    mb_file = _ACCESSOS_DIR / "engine" / "mouse_backend.py"
    imports = _get_module_imports(mb_file)
    assert "ctypes" not in imports
    assert "ctypes.util" not in imports


def test_home_screen_does_not_import_x11_mouse_at_module_level():
    """home_screen.py must not import X11MouseBackend at module level."""
    hs_file = _ACCESSOS_DIR / "home_screen.py"
    tree = ast.parse(hs_file.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and "x11_mouse" in node.module:
            pytest.fail("home_screen.py has top-level import from x11_mouse!")


def test_dry_run_mouse_backend_purely_in_memory():
    """DryRunMouseBackend updates state purely in-memory and is_real_injection is False."""
    from accessos.engine.mouse_backend import DryRunMouseBackend

    events = []
    dry = DryRunMouseBackend(
        screen_size=(1000, 800),
        on_cursor_moved=lambda x, y: events.append(("move", x, y)),
        on_click_event=lambda x, y, b: events.append(("click", x, y, b)),
    )

    assert dry.is_real_injection is False
    assert dry.screen_size == (1000, 800)
    assert dry.get_position() == (500, 400)

    dry.move_to(200, 300)
    assert dry.get_position() == (200, 300)
    assert events[-1] == ("move", 200, 300)

    dry.click(1)
    assert events[-1] == ("click", 200, 300, 1)

    dry.close()


def test_null_mouse_backend_invariants():
    """NullMouseBackend is a safe no-op backend."""
    from accessos.engine.mouse_backend import NullMouseBackend

    null = NullMouseBackend()
    assert null.is_real_injection is False
    null.move_to(100, 100)
    null.click(1)
    null.close()
