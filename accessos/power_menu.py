"""
AccessOS Power Menu
====================
Modal dialog presenting power and session actions.
Phase 2: Every system-changing power action is guarded by an explicit
confirmation dialog before execution.
"""
from __future__ import annotations

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .settings.confirm_dialog import ConfirmDialog
from .settings.system_control import SystemControl

log = logging.getLogger(__name__)


class PowerMenu(Gtk.Dialog):
    """
    Power and session options dialog.
    Guards restart, shutdown, and lock with explicit confirmation dialogs.
    """

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            title="Power Options",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(360, -1)
        self.set_resizable(False)
        self.get_style_context().add_class("settings-card")
        self._build()

    def _build(self) -> None:
        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        # Heading
        heading = Gtk.Label()
        heading.set_markup('<span font="16" weight="bold">Power & Session</span>')
        heading.set_xalign(0.0)
        content.pack_start(heading, False, False, 0)

        sub = Gtk.Label()
        sub.set_markup('<span color="#8b949e" font="10">All power actions require confirmation.</span>')
        sub.set_xalign(0.0)
        content.pack_start(sub, False, False, 0)

        content.pack_start(Gtk.Separator(), False, False, 6)

        # Action buttons
        actions = [
            ("🔒  Lock Screen",    "lock",     False),
            ("🔄  Restart System", "restart",  True),   # destructive
            ("⏻   Shut Down",      "shutdown", True),   # destructive
        ]

        for label, key, destructive in actions:
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("pwr-action-btn-danger" if destructive else "pwr-action-btn")
            btn.connect("clicked", self._on_action, key)
            content.pack_start(btn, False, False, 0)

        content.pack_start(Gtk.Separator(), False, False, 6)

        # Return to Home / Cancel
        home_btn = Gtk.Button(label="🏠  Return to Home")
        home_btn.get_style_context().add_class("btn-cancel")
        home_btn.connect("clicked", lambda _: self.response(Gtk.ResponseType.CANCEL))
        content.pack_start(home_btn, False, False, 0)

        self.show_all()
        home_btn.grab_focus()

    def _on_action(self, _btn: Gtk.Button, key: str) -> None:
        log.info("Power action triggered: %s", key)

        if key == "lock":
            confirmed = ConfirmDialog.ask(
                parent=self,
                title="Lock Session",
                message="Lock AccessOS session now?",
                detail="You will need to re-authenticate to unlock.",
                confirm_label="Lock Now",
                is_destructive=False,
            )
            if confirmed:
                ok, msg = SystemControl.lock_session()
                if not ok:
                    self._show_error("Lock Failed", msg)
                else:
                    self.response(Gtk.ResponseType.OK)

        elif key == "restart":
            confirmed = ConfirmDialog.ask(
                parent=self,
                title="Restart Computer",
                message="Are you sure you want to restart AccessOS?",
                detail="All unsaved work will be lost.",
                confirm_label="Restart Now",
                is_destructive=True,
            )
            if confirmed:
                ok, msg = SystemControl.restart_system()
                if not ok:
                    self._show_error("Restart Failed", msg)
                else:
                    self.response(Gtk.ResponseType.OK)

        elif key == "shutdown":
            confirmed = ConfirmDialog.ask(
                parent=self,
                title="Shut Down Computer",
                message="Are you sure you want to shut down AccessOS?",
                detail="The machine will completely power off.",
                confirm_label="Shut Down Now",
                is_destructive=True,
            )
            if confirmed:
                ok, msg = SystemControl.poweroff_system()
                if not ok:
                    self._show_error("Shutdown Failed", msg)
                else:
                    self.response(Gtk.ResponseType.OK)

    def _show_error(self, title: str, message: str) -> None:
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()
