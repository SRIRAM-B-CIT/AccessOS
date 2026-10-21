"""
Tests for accessos.utils.config.Config
No hardware, no display required.
"""
import tempfile
from pathlib import Path

import pytest

from accessos.utils.config import Config, _DEFAULTS


# ── helpers ────────────────────────────────────────────────────────────────────

def _write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "settings.toml"
    p.write_text(content)
    return p


# ── tests ──────────────────────────────────────────────────────────────────────

class TestConfigDefaults:
    def test_camera_device_default(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("camera", "device") == "/dev/video2"

    def test_sounds_enabled_default(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("audio", "sounds_enabled") is True

    def test_tts_disabled_by_default(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("audio", "tts_enabled") is False

    def test_missing_key_returns_default_arg(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("nonexistent", "key", default="fallback") == "fallback"

    def test_missing_key_returns_none_by_default(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("nonexistent") is None

    def test_accessibility_mode_default(self):
        cfg = Config(config_path=Path("/tmp/nonexistent_accessos_test.toml"))
        assert cfg.get("accessibility", "mode") == "keyboard_mouse"


class TestConfigFileOverride:
    def test_override_camera_device(self, tmp_path):
        p = _write_toml(tmp_path, '[camera]\ndevice = "/dev/video4"\n')
        cfg = Config(config_path=p)
        assert cfg.get("camera", "device") == "/dev/video4"

    def test_override_preserves_other_defaults(self, tmp_path):
        p = _write_toml(tmp_path, '[camera]\ndevice = "/dev/video4"\n')
        cfg = Config(config_path=p)
        # Unrelated key must still be default
        assert cfg.get("audio", "sounds_enabled") is True

    def test_partial_section_override(self, tmp_path):
        p = _write_toml(tmp_path, '[audio]\nvolume = 50\n')
        cfg = Config(config_path=p)
        assert cfg.get("audio", "volume") == 50
        assert cfg.get("audio", "sounds_enabled") is True   # preserved

    def test_malformed_toml_falls_back_to_defaults(self, tmp_path):
        p = tmp_path / "bad.toml"
        p.write_text("[[[ invalid toml !!!")
        # Create a fresh Config with ONLY this bad file — no shared state
        cfg = Config.__new__(Config)
        cfg._data = {}
        from accessos.utils.config import _DEFAULTS
        cfg._deep_merge(cfg._data, _DEFAULTS)
        cfg.config_path = p
        cfg._load_from_file()
        # Must not raise; camera device must still be the default
        assert cfg.get("camera", "device") == "/dev/video2"

    def test_reload(self, tmp_path):
        p = _write_toml(tmp_path, '[audio]\nvolume = 30\n')
        cfg = Config(config_path=p)
        assert cfg.get("audio", "volume") == 30
        p.write_text('[audio]\nvolume = 60\n')
        cfg.reload()
        assert cfg.get("audio", "volume") == 60


class TestDeepMerge:
    def test_deep_merge_does_not_clobber_sibling_keys(self, tmp_path):
        p = _write_toml(tmp_path, '[theme]\nfont_size = 24\n')
        cfg = Config(config_path=p)
        assert cfg.get("theme", "font_size") == 24
        assert cfg.get("theme", "high_contrast") is True   # untouched default
