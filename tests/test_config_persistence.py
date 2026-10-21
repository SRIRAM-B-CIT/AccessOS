"""
Tests for AccessOS Configuration Persistence and Default Restoration
"""
from pathlib import Path
import pytest
from accessos.utils.config import Config, _DEFAULTS


def test_set_and_get(tmp_path):
    p = tmp_path / "test_settings.toml"
    cfg = Config(config_path=p)
    cfg.set("theme", "font_size", value=26)
    assert cfg.get("theme", "font_size") == 26


def test_save_creates_valid_file(tmp_path):
    p = tmp_path / "test_settings.toml"
    cfg = Config(config_path=p)
    cfg.set("accessibility", "dwell_time_ms", value=1800)
    ok = cfg.save()
    assert ok is True
    assert p.exists()

    # Create new instance reading that file
    cfg2 = Config(config_path=p)
    assert cfg2.get("accessibility", "dwell_time_ms") == 1800
    # Other defaults preserved
    assert cfg2.get("camera", "device") == "/dev/video2"


def test_restore_defaults(tmp_path):
    p = tmp_path / "test_settings.toml"
    cfg = Config(config_path=p)
    cfg.set("theme", "font_size", value=99)
    cfg.set("audio", "volume", value=12)
    cfg.save()
    assert cfg.get("theme", "font_size") == 99

    # Restore defaults
    ok = cfg.restore_defaults()
    assert ok is True
    assert cfg.get("theme", "font_size") == 18
    assert cfg.get("audio", "volume") == 80

    # Ensure saved file also reflects restored defaults
    cfg_reloaded = Config(config_path=p)
    assert cfg_reloaded.get("theme", "font_size") == 18


def test_change_listener(tmp_path):
    p = tmp_path / "test_settings.toml"
    cfg = Config(config_path=p)
    events = []

    def on_change(key, val):
        events.append((key, val))

    cfg.add_change_listener(on_change)
    cfg.set("audio", "sounds_enabled", value=False)
    assert len(events) == 1
    assert events[0] == ("audio.sounds_enabled", False)
