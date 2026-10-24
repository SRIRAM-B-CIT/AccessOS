"""
Tests for First-Boot Onboarding Wizard
======================================
Validates:
  - Wizard creation and page navigation
  - Modality selection and staging
  - Hardware permission consent switches
  - Configuration persistence upon completion
"""
from pathlib import Path
from unittest.mock import MagicMock

from accessos.audio_feedback import AudioFeedback
from accessos.onboarding.wizard import OnboardingWizard
from accessos.utils.config import Config
from accessos.voice.tts_engine import TTSEngine


def test_onboarding_wizard_pages_and_navigation(tmp_path: Path):
    cfg_file = tmp_path / "test_settings.toml"
    cfg = Config(config_path=cfg_file)

    mock_tts = MagicMock(spec=TTSEngine)
    mock_audio = MagicMock(spec=AudioFeedback)

    completed = []
    wizard = OnboardingWizard(
        config=cfg,
        tts=mock_tts,
        audio=mock_audio,
        on_complete=lambda: completed.append(True),
    )

    # Initial page is Step 1 (Welcome)
    assert wizard._step_idx == 0
    assert wizard._next_btn.get_label() == "Next →"
    assert wizard._back_btn.get_sensitive() is False

    # Navigate forward
    wizard._on_next_clicked(None)
    assert wizard._step_idx == 1
    assert wizard._back_btn.get_sensitive() is True

    # Navigate to Step 3 (Consent)
    wizard._on_next_clicked(None)
    assert wizard._step_idx == 2

    # Navigate to Step 4 (Display)
    wizard._on_next_clicked(None)
    assert wizard._step_idx == 3

    # Navigate to Step 5 (Finish)
    wizard._on_next_clicked(None)
    assert wizard._step_idx == 4
    assert wizard._next_btn.get_label() == "Start AccessOS ✔"

    # Finish wizard
    wizard._on_next_clicked(None)
    assert len(completed) == 1
    assert cfg.get("system", "first_boot_completed") is True


def test_onboarding_wizard_modality_persistence(tmp_path: Path):
    cfg_file = tmp_path / "test_settings.toml"
    cfg = Config(config_path=cfg_file)

    mock_tts = MagicMock(spec=TTSEngine)
    mock_audio = MagicMock(spec=AudioFeedback)

    wizard = OnboardingWizard(config=cfg, tts=mock_tts, audio=mock_audio)

    # Select head_dwell radio button
    for mode_key, rb in wizard._modality_radios:
        if mode_key == "head_dwell":
            rb.set_active(True)
        else:
            rb.set_active(False)

    wizard._cam_switch.set_active(True)
    wizard._mic_switch.set_active(True)

    wizard._apply_and_finish()

    assert cfg.get("accessibility", "mode") == "head_dwell"
    assert cfg.get("camera", "enabled") is True
    assert cfg.get("voice", "enabled") is True
    assert cfg.get("system", "first_boot_completed") is True
