"""
AccessOS Power Menu
====================
A modal dialog presenting power and session actions.

Phase 1 scope:
  - Lock Screen     : UI placeholder only  (no actual lock in Phase 1)
  - Restart System  : UI placeholder only  (no actual restart in Phase 1)
  - Shut Down       : UI placeholder only  (no actual shutdown in Phase 1)
  - Return to Home  : closes this dialog (always available)

The user-visible message makes the Phase 1 limitation explicit so there is
no false expectation that the button will do anything.

Phase 2 will add privileged power actions after explicit approval.
Destructive actions (restart, shutdown) will always require a confirmation
step before being executed.
"""
from __future__ import annotations

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = logging.getLogger(__name__)

# ── Phase 1 notice text ───────────────────────────────────────────────────────
_PHASE1_MSG = (
    "This action is not yet available.\n\n"
    "Power controls will be implemented in Phase 2, "
    "with a confirmation step before any destructive action.\n\n"
    "To exit AccessOS during development, close the window or press Ctrl+C "
    "in the terminal where it was launched."
)


class PowerMenu(Gtk.Dialog):
    """
    Power and session options dialog.

    Usage::

        menu = PowerMenu(parent=home_window)
        menu.run()
        menu.destroy()
    """

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            title="Power Options",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(340, -1)
        self.set_resizable(False)
        self._build()

    # ── Widget construction ────────────────────────────────────────────────────

    def _build(self) -> None:
        content = self.get_content_area()
        content.set_spacing(0)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_start(8)
        content.set_margin_end(8)

        # Heading
        heading = Gtk.Label()
        heading.set_markup('<span font="15" weight="bold">Power Options</span>')
        heading.set_margin_bottom(12)
        content.pack_start(heading, False, False, 8)

        # Separator
        content.pack_start(Gtk.Separator(), False, False, 0)

        # Action buttons
        actions = [
            ("🔒  Lock Screen",    "lock",     False),
            ("🔄  Restart System", "restart",  True),   # destructive
            ("⏻   Shut Down",      "shutdown", True),   # destructive
        ]

        for label, key, _destructive in actions:
            btn = Gtk.Button(label=label)
            btn.set_margin_top(4)
            btn.set_margin_bottom(4)
            btn.set_margin_start(4)
            btn.set_margin_end(4)
            btn.connect("clicked", self._on_action, key)
            content.pack_start(btn, False, False, 0)

        # Separator
        content.pack_start(Gtk.Separator(), False, False, 4)

        # Return to Home  (always works in Phase 1)
        home_btn = Gtk.Button(label="🏠  Return to Home")
        home_btn.set_margin_top(4)
        home_btn.set_margin_bottom(4)
        home_btn.set_margin_start(4)
        home_btn.set_margin_end(4)
        home_btn.connect("clicked", self._on_return_home)
        content.pack_start(home_btn, False, False, 0)

        # Cancel
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)

        self.show_all()

    # ── Signal handlers ────────────────────────────────────────────────────────

    def _on_action(self, _btn: Gtk.Button, key: str) -> None:
        log.info("Power menu: '%s' pressed — Phase 1 placeholder", key)
        info = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Not available in Phase 1",
        )
        info.format_secondary_text(_PHASE1_MSG)
        info.run()
        info.destroy()

    def _on_return_home(self, _btn: Gtk.Button) -> None:
        log.info("Power menu: returning to home screen")
        self.response(Gtk.ResponseType.CANCEL)
