"""
AccessOS Confirmation Dialog
=============================
An accessible, high-contrast modal dialog that guards system-changing
or destructive actions (reboot, shutdown, restore defaults).
Default focus is ALWAYS set to Cancel for safety.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk


class ConfirmDialog(Gtk.Dialog):
    """
    Guards destructive operations.
    Returns True if user explicitly selects Confirm; False on Cancel or Escape.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        message: str,
        detail: str = "",
        confirm_label: str = "Confirm",
        is_destructive: bool = True,
    ) -> None:
        super().__init__(
            title=title,
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(480, 260)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.get_style_context().add_class("confirm-dialog")

        box = self.get_content_area()
        box.set_spacing(18)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Header with icon
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        icon_name = "dialog-warning" if is_destructive else "dialog-question"
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        header_box.pack_start(icon, False, False, 0)

        title_lbl = Gtk.Label()
        title_lbl.set_markup(f'<span font="16" weight="bold">{title}</span>')
        title_lbl.set_xalign(0.0)
        header_box.pack_start(title_lbl, True, True, 0)
        box.pack_start(header_box, False, False, 0)

        # Message
        msg_lbl = Gtk.Label(label=message)
        msg_lbl.set_xalign(0.0)
        msg_lbl.set_line_wrap(True)
        box.pack_start(msg_lbl, False, False, 0)

        if detail:
            detail_lbl = Gtk.Label()
            detail_lbl.set_markup(f'<span color="#8b949e" font="11">{detail}</span>')
            detail_lbl.set_xalign(0.0)
            detail_lbl.set_line_wrap(True)
            box.pack_start(detail_lbl, False, False, 0)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(12)

        # Cancel button (SAFE DEFAULT — grabs focus)
        cancel_btn = Gtk.Button(label="✕  Cancel")
        cancel_btn.get_style_context().add_class("btn-cancel")
        cancel_btn.set_can_default(True)
        cancel_btn.connect("clicked", lambda _: self.response(Gtk.ResponseType.CANCEL))
        btn_box.pack_start(cancel_btn, False, False, 0)

        # Confirm button
        confirm_btn = Gtk.Button(label=f"✓  {confirm_label}")
        if is_destructive:
            confirm_btn.get_style_context().add_class("btn-danger")
        else:
            confirm_btn.get_style_context().add_class("btn-primary")
        confirm_btn.connect("clicked", lambda _: self.response(Gtk.ResponseType.OK))
        btn_box.pack_start(confirm_btn, False, False, 0)

        box.pack_start(btn_box, False, False, 0)

        self.show_all()
        cancel_btn.grab_focus()

    @classmethod
    def ask(
        cls,
        parent: Gtk.Window,
        title: str,
        message: str,
        detail: str = "",
        confirm_label: str = "Confirm",
        is_destructive: bool = True,
    ) -> bool:
        """Helper to run the dialog modally and return True if confirmed."""
        dlg = cls(
            parent=parent,
            title=title,
            message=message,
            detail=detail,
            confirm_label=confirm_label,
            is_destructive=is_destructive,
        )
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.OK
