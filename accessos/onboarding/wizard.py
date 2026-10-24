"""
AccessOS First-Boot Onboarding Wizard
======================================
Interactive, spoken, accessible setup wizard that configures user input modality,
requests explicit camera/microphone consent, and customizes display preferences.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ..audio_feedback import AudioFeedback
from ..settings.camera_detector import CameraDetector
from ..utils.config import Config
from ..voice.tts_engine import TTSEngine

log = logging.getLogger(__name__)


class OnboardingWizard(Gtk.Window):
    """
    Step-by-step accessible first-boot onboarding wizard.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        tts: Optional[TTSEngine] = None,
        audio: Optional[AudioFeedback] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Welcome to AccessOS — Setup Wizard")
        self.set_default_size(840, 600)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._config = config or Config()
        self._tts = tts or TTSEngine(enabled=True)
        self._audio = audio or AudioFeedback(enabled=True)
        self.on_complete = on_complete

        self._step_idx: int = 0
        self._spoken_enabled: bool = True

        # Config staging
        self._selected_mode: str = "keyboard_mouse"
        self._camera_consent: bool = False
        self._mic_consent: bool = False
        self._font_size: int = 18
        self._high_contrast: bool = True

        self._build_ui()
        self._show_step(0)

    def _build_ui(self) -> None:
        self.get_style_context().add_class("onboarding-window")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_box)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_title("AccessOS Setup")
        header.set_subtitle("First-Boot Accessibility Configuration")
        self.set_titlebar(header)

        # Content Stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._stack.set_transition_duration(250)
        main_box.pack_start(self._stack, True, True, 0)

        # Build pages
        self._page_welcome = self._build_welcome_page()
        self._page_modality = self._build_modality_page()
        self._page_consent = self._build_consent_page()
        self._page_display = self._build_display_page()
        self._page_finish = self._build_finish_page()

        self._stack.add_named(self._page_welcome, "welcome")
        self._stack.add_named(self._page_modality, "modality")
        self._stack.add_named(self._page_consent, "consent")
        self._stack.add_named(self._page_display, "display")
        self._stack.add_named(self._page_finish, "finish")

        # Bottom Navigation Bar
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        nav_box.set_margin_start(24)
        nav_box.set_margin_end(24)
        nav_box.set_margin_top(16)
        nav_box.set_margin_bottom(20)

        self._back_btn = Gtk.Button(label="← Back")
        self._back_btn.set_size_request(120, 48)
        self._back_btn.connect("clicked", self._on_back_clicked)
        nav_box.pack_start(self._back_btn, False, False, 0)

        # Step indicator
        self._step_lbl = Gtk.Label(label="Step 1 of 5")
        self._step_lbl.get_style_context().add_class("dim-label")
        nav_box.pack_start(self._step_lbl, True, True, 0)

        self._next_btn = Gtk.Button(label="Next →")
        self._next_btn.set_size_request(140, 48)
        self._next_btn.get_style_context().add_class("suggested-action")
        self._next_btn.connect("clicked", self._on_next_clicked)
        nav_box.pack_end(self._next_btn, False, False, 0)

        main_box.pack_start(nav_box, False, False, 0)

    # ── Page 1: Welcome ────────────────────────────────────────────────────────

    def _build_welcome_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_start(40)
        box.set_margin_end(40)

        title = Gtk.Label()
        title.set_markup("<span font='24' weight='bold'>Welcome to AccessOS</span>")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label()
        desc.set_markup(
            "<span font='14' color='#c9d1d9'>"
            "AccessOS is an accessible computing environment designed for hands-free, "
            "voice, and adaptive interaction.\n\n"
            "This setup will help configure your preferred interaction methods, "
            "verify camera and microphone permissions, and adjust high-contrast visuals."
            "</span>"
        )
        desc.set_line_wrap(True)
        desc.set_max_width_chars(60)
        box.pack_start(desc, False, False, 0)

        # Spoken Guidance Toggle
        speech_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        speech_box.set_halign(Gtk.Align.CENTER)
        speech_lbl = Gtk.Label(label="Spoken Voice Guidance (Piper TTS):")
        speech_lbl.set_name("speech-guidance-lbl")
        self._speech_switch = Gtk.Switch()
        self._speech_switch.set_active(True)
        self._speech_switch.connect("state-set", self._on_speech_toggled)

        speech_box.pack_start(speech_lbl, False, False, 0)
        speech_box.pack_start(self._speech_switch, False, False, 0)
        box.pack_start(speech_box, False, False, 12)

        return box

    # ── Page 2: Modality Selection ─────────────────────────────────────────────

    def _build_modality_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_margin_top(24)

        title = Gtk.Label()
        title.set_markup("<span font='20' weight='bold'>Select Primary Interaction Mode</span>")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label="Choose how you prefer to control AccessOS. You can change this at any time in Settings.")
        desc.get_style_context().add_class("dim-label")
        box.pack_start(desc, False, False, 0)

        self._modality_radios: list[tuple[str, Gtk.RadioButton]] = []
        modes = [
            ("keyboard_mouse", "⌨️  Keyboard & Physical Mouse", "Standard navigation with arrow keys, numbers 1-6, and mouse clicks."),
            ("voice_only", "🎙️  Voice Control Only", "Hands-free speech commands using offline Vosk speech recognition."),
            ("head_dwell", "🎯  Head Pointer with Dwell Clicking", "Hands-free pointer tracking nose displacement; dwell motionless to click."),
            ("head_blink", "👁️  Head Pointer with Blink Selection", "Head movement controls pointer; deliberate voluntary blink triggers click."),
            ("combined", "⚡  Combined Accessibility (Head + Blink + Voice)", "Head tracking with deliberate blink selection and offline voice commands."),
        ]

        group = None
        for mode_key, mode_title, mode_desc in modes:
            rb = Gtk.RadioButton.new_with_label_from_widget(group, mode_title)
            if group is None:
                group = rb
                rb.set_active(True)

            rb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            rb_box.pack_start(rb, False, False, 0)
            sub_lbl = Gtk.Label(label=f"    {mode_desc}")
            sub_lbl.get_style_context().add_class("dim-label")
            sub_lbl.set_halign(Gtk.Align.START)
            rb_box.pack_start(sub_lbl, False, False, 0)

            box.pack_start(rb_box, False, False, 4)
            self._modality_radios.append((mode_key, rb))

        return box

    # ── Page 3: Device Consent ─────────────────────────────────────────────────

    def _build_consent_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_margin_top(24)

        title = Gtk.Label()
        title.set_markup("<span font='20' weight='bold'>Hardware Permissions &amp; Consent</span>")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(
            label="AccessOS processes camera and microphone streams 100% locally in-memory.\n"
                  "No images, video, or audio are ever stored, uploaded, or shared."
        )
        desc.get_style_context().add_class("dim-label")
        box.pack_start(desc, False, False, 0)

        # Camera section
        cam_rec = CameraDetector().get_recommended_camera()
        cam_name = cam_rec.name if cam_rec else "Integrated RGB Camera"
        cam_node = cam_rec.device_node if cam_rec else "/dev/video2"

        cam_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        cam_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cam_title = Gtk.Label()
        cam_title.set_markup(f"<b>Enable Camera Tracking</b> ({cam_name})")
        cam_title.set_halign(Gtk.Align.START)
        cam_sub = Gtk.Label(label=f"Required for head pointer, dwell, and blink detection. Node: {cam_node}")
        cam_sub.get_style_context().add_class("dim-label")
        cam_sub.set_halign(Gtk.Align.START)
        cam_info.pack_start(cam_title, False, False, 0)
        cam_info.pack_start(cam_sub, False, False, 0)
        cam_box.pack_start(cam_info, True, True, 0)

        self._cam_switch = Gtk.Switch()
        self._cam_switch.set_active(False)
        cam_box.pack_end(self._cam_switch, False, False, 0)
        box.pack_start(cam_box, False, False, 6)

        # Microphone section
        mic_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        mic_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        mic_title = Gtk.Label()
        mic_title.set_markup("<b>Enable Microphone Listening</b>")
        mic_title.set_halign(Gtk.Align.START)
        mic_sub = Gtk.Label(label="Required for offline voice commands. Microphone stays paused until you unpause.")
        mic_sub.get_style_context().add_class("dim-label")
        mic_sub.set_halign(Gtk.Align.START)
        mic_info.pack_start(mic_title, False, False, 0)
        mic_info.pack_start(mic_sub, False, False, 0)
        mic_box.pack_start(mic_info, True, True, 0)

        self._mic_switch = Gtk.Switch()
        self._mic_switch.set_active(False)
        mic_box.pack_end(self._mic_switch, False, False, 0)
        box.pack_start(mic_box, False, False, 6)

        return box

    # ── Page 4: Visuals & Audio ────────────────────────────────────────────────

    def _build_display_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_margin_top(24)

        title = Gtk.Label()
        title.set_markup("<span font='20' weight='bold'>Visual &amp; Sound Feedback</span>")
        box.pack_start(title, False, False, 0)

        # High Contrast
        hc_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        hc_lbl = Gtk.Label()
        hc_lbl.set_markup("<b>High Contrast Mode</b> (Enhanced borders and focal indicators)")
        hc_box.pack_start(hc_lbl, True, True, 0)
        self._hc_switch = Gtk.Switch()
        self._hc_switch.set_active(True)
        hc_box.pack_end(self._hc_switch, False, False, 0)
        box.pack_start(hc_box, False, False, 6)

        # Font Size
        fs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        fs_lbl = Gtk.Label()
        fs_lbl.set_markup("<b>Base Font Size</b>")
        fs_box.pack_start(fs_lbl, True, True, 0)

        self._fs_combo = Gtk.ComboBoxText()
        self._fs_combo.append("16", "Standard (16pt)")
        self._fs_combo.append("18", "Large (18pt - Recommended)")
        self._fs_combo.append("22", "Extra Large (22pt)")
        self._fs_combo.set_active_id("18")
        fs_box.pack_end(self._fs_combo, False, False, 0)
        box.pack_start(fs_box, False, False, 6)

        # Audio Test Button
        snd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        snd_lbl = Gtk.Label()
        snd_lbl.set_markup("<b>Audio Feedback Test</b>")
        snd_box.pack_start(snd_lbl, True, True, 0)

        test_snd_btn = Gtk.Button(label="🔊 Test Sound")
        test_snd_btn.connect("clicked", lambda _: self._audio.play("activate"))
        snd_box.pack_end(test_snd_btn, False, False, 0)
        box.pack_start(snd_box, False, False, 6)

        return box

    # ── Page 5: Finish ─────────────────────────────────────────────────────────

    def _build_finish_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_start(40)
        box.set_margin_end(40)

        title = Gtk.Label()
        title.set_markup("<span font='24' weight='bold'>Setup Complete!</span>")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label()
        desc.set_markup(
            "<span font='14' color='#c9d1d9'>"
            "Your preferences have been configured.\n\n"
            "Key shortcuts to remember:\n"
            "• <b>F12</b>: Emergency Stop all tracking\n"
            "• <b>Esc</b>: Pause control immediately\n"
            "• <b>R</b>: Resume control\n"
            "• <b>Ctrl+R</b>: Open Document Reader\n"
            "• <b>Ctrl+Alt+T</b>: Emergency Terminal\n\n"
            "Click 'Start AccessOS' to begin."
            "</span>"
        )
        desc.set_line_wrap(True)
        box.pack_start(desc, False, False, 0)

        return box

    # ── Navigation & Stepping ──────────────────────────────────────────────────

    def _show_step(self, step: int) -> None:
        self._step_idx = step
        pages = ["welcome", "modality", "consent", "display", "finish"]
        self._stack.set_visible_child_name(pages[step])

        self._step_lbl.set_text(f"Step {step + 1} of 5")
        self._back_btn.set_sensitive(step > 0)

        if step == len(pages) - 1:
            self._next_btn.set_label("Start AccessOS ✔")
        else:
            self._next_btn.set_label("Next →")

        # Spoken guidance for active step
        if self._spoken_enabled and self._tts:
            prompts = [
                "Welcome to AccessOS. Press Next to configure your interaction settings.",
                "Select your preferred interaction mode: Keyboard and mouse, Voice control, or Head tracking.",
                "Review hardware permissions for camera and microphone.",
                "Adjust visual contrast, font size, and sound feedback.",
                "Setup is complete. Press Start AccessOS to enter your desktop.",
            ]
            self._tts.speak(prompts[step], interrupt=True)

    def _on_next_clicked(self, _btn) -> None:
        if self._step_idx < 4:
            self._show_step(self._step_idx + 1)
        else:
            self._apply_and_finish()

    def _on_back_clicked(self, _btn) -> None:
        if self._step_idx > 0:
            self._show_step(self._step_idx - 1)

    def _on_speech_toggled(self, _switch, state: bool) -> bool:
        self._spoken_enabled = state
        return False

    def _apply_and_finish(self) -> None:
        """Save settings and mark first boot completed."""
        # Find selected mode
        for mode_key, rb in self._modality_radios:
            if rb.get_active():
                self._selected_mode = mode_key
                break

        # Save to config
        self._config.set("accessibility", "mode", value=self._selected_mode)
        self._config.set("camera", "enabled", value=self._cam_switch.get_active())
        self._config.set("voice", "enabled", value=self._mic_switch.get_active())
        self._config.set("theme", "high_contrast", value=self._hc_switch.get_active())

        fs_id = self._fs_combo.get_active_id() or "18"
        self._config.set("theme", "font_size", value=int(fs_id))

        # Mark first boot completed
        self._config.set("system", "first_boot_completed", value=True)
        self._config.save()

        log.info("Onboarding wizard completed with mode: %s, camera: %s, voice: %s",
                 self._selected_mode, self._cam_switch.get_active(), self._mic_switch.get_active())

        if self.on_complete:
            try:
                self.on_complete()
            except Exception as exc:
                log.error("on_complete error: %s", exc)

        self.destroy()
