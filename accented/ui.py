"""Native Adwaita UI with GameBridge's centered, single-panel composition."""
from __future__ import annotations
import os
from pathlib import Path
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from .core import AccentStore, PRESETS, normalize_hex, foreground, nearest_preset, rgb
from .desktop import GnomeSettings, PixelPicker

APP_ID = "com.loew.accented"
ROOT = Path(__file__).resolve().parent.parent
CSS = """
.accented-content .main-panel { padding: 24px; }
.accented-content .color-swatch { border-radius: 12px; }
.accented-content .swatch-button { padding: 8px; }
.accented-content .small-swatch { border-radius: 6px; }
.accented-content .picker-actions > flowboxchild { padding: 0; }
.accented-content .recent-colors > flowboxchild { padding: 0; }
"""


def label(text, *classes, center=False):
    widget = Gtk.Label(label=text, xalign=0.5 if center else 0)
    widget.set_wrap(True)
    widget.set_justify(Gtk.Justification.CENTER if center else Gtk.Justification.LEFT)
    for name in classes:
        widget.add_css_class(name)
    return widget


def button(text, callback, *, icon=None):
    widget = Gtk.Button()
    if icon:
        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        row.append(Gtk.Image.new_from_icon_name(icon))
        row.append(Gtk.Label(label=text))
        widget.set_child(row)
    else:
        widget.set_label(text)
    widget.set_tooltip_text(text)
    widget.update_property([Gtk.AccessibleProperty.LABEL], [text])
    widget.connect("clicked", callback)
    return widget


class Accented(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        self.settings = GnomeSettings()
        self.store = AccentStore(Path(GLib.get_user_config_dir()),
                                 Path(GLib.get_user_state_dir()), self.settings)
        self.color = PRESETS["blue"]
        self.valid = True
        self.busy = False
        self.picker = None
        self.dialog = None
        self.issue = None
        self.saved_state = {}
        self.providers = []

    def do_startup(self):
        Adw.Application.do_startup(self)
        for name, fn, shortcuts in (
            ("quit", lambda *_: self.window.close(), ["<Primary>q"]),
            ("pick", self.pick_screen, ["<Primary>p"]),
            ("choose", self.choose_color, ["<Primary>o"]),
            ("apply", self.apply, ["<Primary>Return"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", fn)
            self.add_action(action)
            self.set_accels_for_action("app." + name, shortcuts)

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        try:
            self.saved_state = self.store.state()
            self.color = normalize_hex(self.saved_state.get("color", self.color))
        except Exception as exc:
            self.issue = str(exc)
        self.window = Adw.ApplicationWindow(application=self, title="Accented",
                                             default_width=620, default_height=740)
        self.window.set_icon_name(APP_ID)
        self.window.connect("close-request", self.close_requested)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.set_content(root)
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        # Leave native window controls and title placement to Adwaita.
        root.append(header)
        self.scroll = Gtk.ScrolledWindow(vexpand=True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        root.append(self.scroll)
        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=500)
        self.scroll.set_child(clamp)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.add_css_class("accented-content")
        for edge, value in (("top", 12), ("bottom", 32), ("start", 32), ("end", 32)):
            getattr(self.content, "set_margin_" + edge)(value)
        clamp.set_child(self.content)
        self.hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.hero.set_margin_bottom(24)
        image_path = ROOT / "assets" / (APP_ID + ".png")
        if image_path.is_file():
            image = Gtk.Image.new_from_file(str(image_path))
        else:
            image = Gtk.Image.new_from_icon_name("applications-graphics-symbolic")
        image.set_pixel_size(64)
        image.set_halign(Gtk.Align.CENTER)
        self.hero.append(image)
        self.hero.append(label("Accented", "title-1", center=True))
        self.hero.append(label("Pick a pixel. Make it your accent.", center=True))
        self.content.append(self.hero)

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.panel.add_css_class("card")
        self.panel.add_css_class("main-panel")
        self.content.append(self.panel)
        selected = Gtk.Box(spacing=16)
        self.swatch = Gtk.Box(width_request=56, height_request=56, valign=Gtk.Align.CENTER)
        self.swatch.add_css_class("color-swatch")
        selected.append(self.swatch)
        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
        hex_label = Gtk.Label(label="_Hex color", use_underline=True, xalign=0)
        fields.append(hex_label)
        entry_row = Gtk.Box(spacing=8)
        self.entry = Gtk.Entry(text=self.color, placeholder_text="#DB805A", max_length=7,
                               width_chars=9, hexpand=True)
        self.entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self.entry.set_tooltip_text("Enter a six-digit or three-digit hex color")
        hex_label.set_mnemonic_widget(self.entry)
        self.entry.connect("changed", self.entry_changed)
        self.entry.connect("activate", self.normalize_entry)
        entry_row.append(self.entry)
        self.copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        self.copy.set_tooltip_text("Copy hex color")
        self.copy.update_property([Gtk.AccessibleProperty.LABEL], ["Copy hex color"])
        self.copy.connect("clicked", self.copy_color)
        entry_row.append(self.copy)
        fields.append(entry_row)
        selected.append(fields)
        self.panel.append(selected)
        self.validation = label("", "error")
        self.validation.set_visible(False)
        self.panel.append(self.validation)

        self.picker_actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=1, max_children_per_line=2, homogeneous=True,
            column_spacing=12, row_spacing=12)
        self.picker_actions.add_css_class("picker-actions")
        self.choose_button = button("Choose Color", self.choose_color, icon="applications-graphics-symbolic")
        self.pick_button = button("Pick from Screen", self.pick_screen, icon="color-select-symbolic")
        self.picker_actions.append(self.choose_button)
        self.picker_actions.append(self.pick_button)
        self.panel.append(self.picker_actions)

        self.preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.preview.add_css_class("accented-preview")
        self.preview.append(label("Preview", "heading"))
        sample_row = Gtk.Box(spacing=12)
        self.sample_button = button("Sample", lambda *_: self.message("This is a preview. Your desktop has not changed."))
        self.sample_button.add_css_class("suggested-action")
        sample_row.append(self.sample_button)
        self.sample_check = Gtk.CheckButton(label="Selected", active=True)
        sample_row.append(self.sample_check)
        self.preview.append(sample_row)
        self.panel.append(self.preview)

        self.recent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.recent_box.append(label("Recent colors", "heading"))
        self.recents = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=1, max_children_per_line=8,
            column_spacing=4, row_spacing=4)
        self.recents.add_css_class("recent-colors")
        self.recent_box.append(self.recents)
        self.panel.append(self.recent_box)

        options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        options.set_margin_top(20)
        self.match = Gtk.CheckButton(label="Match desktop to nearest GNOME color")
        self.match.get_child().set_wrap(True)
        self.match.set_active(self.saved_state.get("shell_applied") is not None)
        self.match.set_sensitive(self.settings.available)
        self.match.connect("toggled", self.option_changed)
        options.append(self.match)
        self.match_hint = label("")
        self.match_hint.set_margin_start(28)
        options.append(self.match_hint)
        self.content.append(options)

        controls = Gtk.Box(spacing=12, homogeneous=True)
        controls.set_margin_top(20)
        self.restore_button = button("Restore", self.restore)
        self.apply_button = button("Apply Accent", self.apply)
        self.apply_button.add_css_class("suggested-action")
        controls.append(self.restore_button)
        controls.append(self.apply_button)
        self.content.append(controls)
        status_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        status_row.set_margin_top(12)
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        status_row.append(self.spinner)
        self.status = label("", center=True)
        self.status.set_hexpand(True)
        self.status.set_selectable(True)
        status_row.append(self.status)
        self.content.append(status_row)

        details = Gtk.Expander(label="What changes?")
        details.set_margin_top(20)
        info = label(
            "Your color is applied to GTK 3 and GTK 4 apps that honor user CSS. "
            "Reopen apps to see changes. Sandboxed Flatpak, Qt, Electron, and custom-drawn apps may not follow it.\n\n"
            "Desktop matching uses GNOME’s nearest built-in color, not your exact hex value. "
            "This does not add swatches to GNOME Settings.\n\n"
            "Only accent colors change, not your theme or wallpaper. Existing CSS is kept. "
            "Accented backs up each change and refuses to overwrite symbolic links or externally edited accent blocks.\n\n"
            "For older GTK apps, reapply after switching light/dark mode to refresh accent-text contrast.\n\n"
            "Keyboard: Ctrl+O chooses a color, Ctrl+P picks a pixel, Ctrl+Enter applies, Ctrl+Q closes."
        )
        info.set_margin_top(12)
        info.set_selectable(True)
        details.set_child(info)
        self.content.append(details)
        self.preview_provider = Gtk.CssProvider()
        self.swatch_provider = Gtk.CssProvider()
        self.add_css(CSS)
        for provider in (self.preview_provider, self.swatch_provider):
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.style = Adw.StyleManager.get_default()
        self.style.connect("notify::dark", self.theme_changed)
        self.style.connect("notify::high-contrast", self.theme_changed)
        self.render_recents()
        self.update_preview()
        self.update_controls()
        self.message(self.issue or ("An interrupted change needs Restore." if self.store.journal.exists()
                                    else "Preview only. Apply when you’re ready."), error=bool(self.issue))
        self.window.present()

    def add_css(self, css):
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.providers.append(provider)

    def render_recents(self):
        child = self.recents.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.recents.remove(child)
            child = next_child
        recent = self.saved_state.get("recent", [])[:8]
        self.recent_box.set_visible(bool(recent))
        for i, color in enumerate(recent):
            color = normalize_hex(color)
            item = button(color, lambda _b, c=color: self.set_color(c))
            item.set_tooltip_text("Use " + color)
            item.add_css_class("swatch-button")
            patch = Gtk.Box(width_request=20, height_request=20)
            patch.add_css_class("small-swatch")
            patch.add_css_class("recent-" + str(i))
            item.set_child(patch)
            item.update_property([Gtk.AccessibleProperty.LABEL], ["Use recent color " + color])
            # One small scoped provider per palette slot, replaced on refresh below.
            self.recents.append(item)
        css = "\n".join(f".recent-{i} {{ background-color: {normalize_hex(c)}; "
                         "box-shadow: inset 0 0 0 1px alpha(currentColor, 0.2); }"
                         for i, c in enumerate(recent))
        if not hasattr(self, "recent_provider"):
            self.recent_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.recent_provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.recent_provider.load_from_data(css.encode())

    def entry_changed(self, *_):
        try:
            value = normalize_hex(self.entry.get_text())
        except ValueError:
            self.valid = False
            self.entry.add_css_class("error")
            self.validation.set_text("Use a hex color such as #DB805A or #DA8.")
            self.validation.set_visible(True)
        else:
            self.valid = True
            self.color = value
            self.entry.remove_css_class("error")
            self.validation.set_visible(False)
            if hasattr(self, "preview_provider"):
                self.update_preview()
        if hasattr(self, "apply_button"):
            self.update_controls()

    def normalize_entry(self, *_):
        if self.valid:
            self.entry.set_text(self.color)

    def set_color(self, color):
        self.entry.set_text(normalize_hex(color))
        self.message("Preview only. Apply when you’re ready.")

    def update_preview(self):
        fg = foreground(self.color)
        self.swatch_provider.load_from_data((
            f".color-swatch {{ background-color: {self.color}; "
            "box-shadow: inset 0 0 0 1px alpha(currentColor, 0.2); }"
        ).encode())
        if self.style.get_high_contrast():
            css = ""
        elif Gtk.get_minor_version() >= 16 and Adw.get_minor_version() >= 6:
            css = (f".accented-preview {{ --accent-bg-color: {self.color}; --accent-fg-color: {fg}; "
                   "--accent-color: oklab(from var(--accent-bg-color) var(--standalone-color-oklab)); }")
        else:
            css = (f".accented-preview .suggested-action, .accented-preview check:checked {{ "
                   f"background-color: {self.color}; color: {fg}; }}")
        self.preview_provider.load_from_data(css.encode())
        self.update_match_hint()

    def update_match_hint(self):
        if not self.settings.available:
            text = "Desktop matching is unavailable in this session. App accents still work."
        elif self.match.get_active():
            text = f"Nearest desktop color: {nearest_preset(self.color).title()}. This is an approximation."
        elif self.saved_state.get("shell_applied") is not None:
            text = "Off. Apply will restore your previous desktop match if it is still owned."
        else:
            text = "Off. Your GNOME desktop accent stays as it is."
        self.match_hint.set_text(text)

    def option_changed(self, *_):
        if hasattr(self, "match_hint"):
            self.update_match_hint()
        if hasattr(self, "apply_button"):
            self.update_controls()

    def theme_changed(self, *_):
        self.update_preview()
        self.message("Appearance changed. Reapply to refresh older GTK apps’ accent-text contrast.")

    def update_controls(self):
        for widget in (self.entry, self.choose_button, self.pick_button):
            widget.set_sensitive(not self.busy)
        self.match.set_sensitive(not self.busy and self.settings.available)
        self.copy.set_sensitive(not self.busy and self.valid)
        self.recents.set_sensitive(not self.busy)
        self.apply_button.set_sensitive(not self.busy and self.valid and not self.issue
                                        and not self.store.journal.exists())
        self.restore_button.set_sensitive(not self.busy and
            (bool(self.saved_state.get("files")) or self.store.journal.exists()))

    def message(self, text, error=False):
        self.status.set_text(text)
        if error:
            self.status.add_css_class("error")
        else:
            self.status.remove_css_class("error")
        if hasattr(self.status, "announce"):
            self.status.announce(text, Gtk.AccessibleAnnouncementPriority.POLITE)

    def copy_color(self, *_):
        if self.valid:
            Gdk.Display.get_default().get_clipboard().set(self.color)
            self.message("Copied " + self.color)

    def choose_color(self, *_):
        if self.busy or self.dialog:
            return
        color = Gdk.RGBA()
        color.parse(self.color)
        self.dialog = Gtk.ColorDialog(title="Choose an accent", with_alpha=False, modal=True)
        self.dialog.choose_rgba(self.window, color, None, self.color_chosen)

    def color_chosen(self, dialog, result):
        try:
            chosen = dialog.choose_rgba_finish(result)
            from .core import from_rgb
            self.set_color(from_rgb((chosen.red, chosen.green, chosen.blue)))
        except GLib.Error as exc:
            if not exc.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                self.message("Color chooser: " + exc.message, error=True)
        finally:
            self.dialog = None

    def pick_screen(self, *_):
        if self.busy or self.dialog:
            return
        self.busy = True
        self.update_controls()
        self.hold()
        self.picker = PixelPicker(self.pixel_chosen)
        self.window.set_visible(False)
        # Let the compositor reveal the wallpaper before entering pixel-pick mode.
        GLib.timeout_add(200, self.picker.start)

    def pixel_chosen(self, color, message):
        self.picker = None
        self.busy = False
        self.window.present()
        self.release()
        if color:
            self.set_color(color)
        else:
            self.message(message or "Nothing was changed.")
        self.update_controls()

    def run_change(self, operation, description):
        if self.busy:
            return
        self.busy = True
        self.spinner.set_visible(True)
        self.spinner.start()
        self.message(description)
        self.update_controls()
        def worker():
            try:
                message = operation()
                state = self.store.state()
            except Exception as exc:
                GLib.idle_add(self.change_done, None, str(exc), None)
            else:
                GLib.idle_add(self.change_done, message, None, state)
        threading.Thread(target=worker, daemon=False).start()

    def change_done(self, text, error, state):
        self.busy = False
        self.spinner.stop()
        self.spinner.set_visible(False)
        if state is not None:
            self.saved_state = state
            self.issue = None
            self.match.set_active(state.get("shell_applied") is not None)
            self.render_recents()
        self.message(error or text, error=bool(error))
        self.update_controls()
        return False

    def apply(self, *_):
        if self.busy or not self.valid or self.issue or self.store.journal.exists():
            return
        self.normalize_entry()
        color = self.color
        match = self.match.get_active()
        dark = self.style.get_dark()
        def operation():
            self.store.apply(color, modern=Gtk.get_minor_version() >= 16, dark=dark, match_shell=match)
            return f"Applied {color}. Reopen apps to see the change."
        self.run_change(operation, "Backing up and applying…")

    def restore(self, *_):
        self.run_change(lambda: self.store.restore()[1], "Restoring your previous accents…")

    def close_requested(self, *_):
        if self.busy:
            self.message("A change is in progress. The window will stay open until it finishes.")
            return True
        return False
