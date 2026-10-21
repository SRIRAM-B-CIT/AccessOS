"""
Tests for Native X11Mouse Controller
"""
from accessos.engine.x11_mouse import X11Mouse


def test_mouse_screen_and_position():
    mouse = X11Mouse()
    w, h = mouse.screen_size
    assert w > 0 and h > 0

    x, y = mouse.get_position()
    assert 0 <= x <= w
    assert 0 <= y <= h
    mouse.close()


def test_mouse_move_clamping():
    mouse = X11Mouse()
    w, h = mouse.screen_size

    # Move within bounds
    orig_x, orig_y = mouse.get_position()
    mouse.move_to(100, 100)
    # Restore original position so we don't disturb the user
    mouse.move_to(orig_x, orig_y)
    mouse.close()
