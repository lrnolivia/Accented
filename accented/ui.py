"""Compact native Adwaita UI with GameBridge's centered composition."""
from __future__ import annotations

from pathlib import Path
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import __version__
from .core import AccentStore, PRESETS, normalize_hex, nearest_preset
from .desktop import GnomeSettings, PixelPicker

APP_ID = "com.loew.accented"
ROOT = Path(__file__).resolve().parent.parent
RELEASES_URL = "https://github.com/lrnolivia/Accented/releases/latest"

CSS = """
.accented-content .main-panel { padding: 24px; }
.accented-content .color-swatch { border-radius: 12px; }
.accented-content .swatch-button { padding: 8px; }
.accented-content .small-swatch { border-radius: 6px; }
.accented-content .picker-actions > flowboxchild { padding: 0; }
.accented-content .recent-colors > flowboxchild { padding: 0; }
.accented-scroll { border: none; box-shadow: none; }
.accented-scroll undershoot,
.accented-scroll overshoot { background: transparent; box-shadow: none; }
"""


def label(text, *classes, center=False):
    widget = Gtk.Label(label=text, xalign=0.5 if center else 0)
    widget.set_wrap(True)
    widget.set_justify(Gtk.Justification.CENTER if center else Gtk.Justification.LEFT)
    for name in classes:
        widget.add_css_class(name)
    return widget


def menu_item(text, action, icon):
    item = Gio.MenuItem.new(text, action)
    item.set_icon(Gio.ThemedIcon.new(icon))
    return item


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
        self.store = AccentStore(
            Path(GLib.get_user_config_dir()),
            Path(GLib.get_user_state_dir()),
            self.settings,
        )
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

        actions = (
            ("quit", lambda *_: self.window.close(), ["<Primary>q"]),
            ("pick", self.pick_screen, ["<Primary>p"]),
            ("choose", self.choose_color, ["<Primary>o"]),
            ("apply", self.apply, ["<Primary>Return"]),
            ("restore", self.restore, []),
            ("check-updates", self.check_updates, []),
            ("what-changes", self.show_what_changes, []),
            ("about", self.show_about, []),
        )
        for name, fn, shortcuts in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", fn)
            self.add_action(action)
            if shortcuts:
                self.set_accels_for_action("app." + name, shortcuts)

        self.restore_action = self.lookup_action("restore")
        self.check_update_action = self.lookup_action("check-updates")

        self.match_action = Gio.SimpleAction.new_stateful(
            "match-desktop", None, GLib.Variant.new_boolean(False)
        )
        self.match_action.connect("change-state", self.match_desktop_changed)
        self.add_action(self.match_action)

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        try:
            self.saved_state = self.store.state()
            self.color = normalize_hex(self.saved_state.get("color", self.color))
        except Exception as exc:
            self.issue = str(exc)

        self.match_action.set_state(
            GLib.Variant.new_boolean(self.saved_state.get("shell_applied") is not None)
        )
        self.match_action.set_enabled(self.settings.available)

        self.window = Adw.ApplicationWindow(
            application=self,
            title="Accented",
            default_width=560,
            default_height=440,
        )
        self.window.set_icon_name(APP_ID)
        self.window.connect("close-request", self.close_requested)

        self.toast_overlay = Adw.ToastOverlay()
        self.window.set_content(self.toast_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(root)

        header = Adw.HeaderBar()
        header.add_css_class("flat")
        self.menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Accented options",
            menu_model=self.build_menu(),
        )
        self.menu_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Accented options"]
        )
        header.pack_end(self.menu_button)
        root.append(header)

        self.scroll = Gtk.ScrolledWindow(vexpand=True)
        self.scroll.add_css_class("accented-scroll")
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
        image = (
            Gtk.Image.new_from_file(str(image_path))
            if image_path.is_file()
            else Gtk.Image.new_from_icon_name("applications-graphics-symbolic")
        )
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
        self.entry = Gtk.Entry(
            text=self.color,
            placeholder_text="#DB805A",
            max_length=7,
            width_chars=9,
            hexpand=True,
        )
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

        self.picker_actions = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=1,
            max_children_per_line=2,
            homogeneous=True,
            column_spacing=12,
            row_spacing=12,
        )
        self.picker_actions.add_css_class("picker-actions")
        self.choose_button = button(
            "Choose Color", self.choose_color, icon="applications-graphics-symbolic"
        )
        self.pick_button = button(
            "Pick from Screen", self.pick_screen, icon="color-select-symbolic"
        )
        self.picker_actions.append(self.choose_button)
        self.picker_actions.append(self.pick_button)
        self.panel.append(self.picker_actions)

        self.recent_expander = Gtk.Expander(label="Recent colors")
        self.recent_expander.set_expanded(False)
        self.recents = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=1,
            max_children_per_line=8,
            column_spacing=4,
            row_spacing=4,
        )
        self.recents.set_margin_top(10)
        self.recents.add_css_class("recent-colors")
        self.recent_expander.set_child(self.recents)
        self.panel.append(self.recent_expander)

        self.apply_button = button("Apply Accent", self.apply)
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.set_hexpand(True)
        self.panel.append(self.apply_button)

        self.swatch_provider = Gtk.CssProvider()
        self.add_css(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.swatch_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.style = Adw.StyleManager.get_default()
        self.style.connect("notify::dark", self.theme_changed)
        self.style.connect("notify::high-contrast", self.theme_changed)

        self.render_recents()
        self.update_swatch()
        self.update_controls()

        self.window.present()
        if self.issue:
            self.message(self.issue, error=True)
        elif self.store.journal.exists():
            self.message("An interrupted change needs Restore from the menu.", error=True)

    def build_menu(self):
        menu = Gio.Menu()

        color_section = Gio.Menu()
        color_section.append_item(menu_item(
            "Match GNOME Desktop", "app.match-desktop",
            "preferences-desktop-appearance-symbolic"))
        color_section.append_item(menu_item(
            "Restore Original Accent", "app.restore", "edit-undo-symbolic"))
        menu.append_section(None, color_section)

        update_section = Gio.Menu()
        update_section.append_item(menu_item(
            "Check for Updates…", "app.check-updates", "view-refresh-symbolic"))
        menu.append_section(None, update_section)

        help_section = Gio.Menu()
        help_section.append_item(menu_item(
            "What Changes?", "app.what-changes", "dialog-information-symbolic"))
        help_section.append_item(menu_item(
            "About Accented", "app.about", "help-about-symbolic"))
        menu.append_section(None, help_section)
        return menu

    def add_css(self, css):
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.providers.append(provider)

    def toast(self, text, timeout=3):
        if not self.window:
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def render_recents(self):
        child = self.recents.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.recents.remove(child)
            child = next_child

        recent = self.saved_state.get("recent", [])[:8]
        self.recent_expander.set_visible(bool(recent))

        for i, color in enumerate(recent):
            color = normalize_hex(color)
            item = button(color, lambda _b, c=color: self.set_color(c))
            item.set_tooltip_text("Use " + color)
            item.add_css_class("swatch-button")
            patch = Gtk.Box(width_request=20, height_request=20)
            patch.add_css_class("small-swatch")
            patch.add_css_class("recent-" + str(i))
            item.set_child(patch)
            item.update_property(
                [Gtk.AccessibleProperty.LABEL], ["Use recent color " + color]
            )
            self.recents.append(item)

        css = "\n".join(
            f".recent-{i} {{ background-color: {normalize_hex(c)}; "
            "box-shadow: inset 0 0 0 1px alpha(currentColor, 0.2); }"
            for i, c in enumerate(recent)
        )
        if not hasattr(self, "recent_provider"):
            self.recent_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                self.recent_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
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
            if hasattr(self, "swatch_provider"):
                self.update_swatch()
        if hasattr(self, "apply_button"):
            self.update_controls()

    def normalize_entry(self, *_):
        if self.valid:
            self.entry.set_text(self.color)

    def set_color(self, color):
        self.entry.set_text(normalize_hex(color))
        self.message("Selected " + self.color + ".", timeout=2)

    def update_swatch(self):
        self.swatch_provider.load_from_data(
            (
                f".color-swatch {{ background-color: {self.color}; "
                "box-shadow: inset 0 0 0 1px alpha(currentColor, 0.2); }"
            ).encode()
        )

    def match_desktop_changed(self, action, value):
        enabled = value.get_boolean()
        action.set_state(value)
        if self.window:
            if not self.settings.available:
                self.toast("GNOME desktop matching is unavailable in this session.")
                action.set_state(GLib.Variant.new_boolean(False))
            elif enabled:
                self.toast("Desktop match on. Apply will use GNOME’s nearest built-in color.")
            else:
                self.toast("Desktop match off. Apply will restore Accented’s owned match.")
        self.update_controls()

    def theme_changed(self, *_):
        self.message(
            "Appearance changed. Reapply to refresh older GTK apps’ accent-text contrast.",
            timeout=5,
        )

    def update_controls(self):
        for widget in (self.entry, self.choose_button, self.pick_button):
            widget.set_sensitive(not self.busy)
        self.copy.set_sensitive(not self.busy and self.valid)
        self.recents.set_sensitive(not self.busy)
        self.apply_button.set_sensitive(
            not self.busy
           
            and self.valid
            and not self.issue
            and not self.store.journal.exists()
        )
        restorable = bool(self.saved_state.get("files")) or self.store.journal.exists()
        self.restore_action.set_enabled(not self.busy and restorable)
        self.match_action.set_enabled(
            not self.busy and self.settings.available
        )
        self.check_update_action.set_enabled(not self.busy)

    def message(self, text, error=False, timeout=4):
        if not text:
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(timeout)
        if error:
            toast.set_priority(Adw.ToastPriority.HIGH)
        self.toast_overlay.add_toast(toast)

    def copy_color(self, *_):
        if self.valid:
            Gdk.Display.get_default().get_clipboard().set(self.color)
            self.toast("Copied " + self.color)

    def choose_color(self, *_):
        if self.busy or self.dialog:
            return
        color = Gdk.RGBA()
        color.parse(self.color)
        self.dialog = Gtk.ColorDialog(
            title="Choose an accent", with_alpha=False, modal=True
        )
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
        self.message(description, timeout=2)
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
        if state is not None:
            self.saved_state = state
            self.issue = None
            self.match_action.set_state(
                GLib.Variant.new_boolean(state.get("shell_applied") is not None)
            )
            self.render_recents()
        self.message(error or text, error=bool(error))
        self.update_controls()
        return False

    def apply(self, *_):
        if (
            self.busy
            or not self.valid
            or self.issue
            or self.store.journal.exists()
        ):
            return
        self.normalize_entry()
        color = self.color
        match = self.match_action.get_state().get_boolean()
        dark = self.style.get_dark()

        def operation():
            self.store.apply(
                color,
                modern=Gtk.get_minor_version() >= 16,
                dark=dark,
                match_shell=match,
            )
            if match:
                preset = nearest_preset(color).title()
                return (
                    f"Applied {color}. GNOME desktop matched live to {preset}; "
                    "reopen apps for the exact GTK color."
                )
            return f"Applied {color}. Reopen apps to see the change."

        self.run_change(operation, "Backing up and applying…")

    def restore(self, *_):
        self.run_change(
            lambda: self.store.restore()[1],
            "Restoring your previous accents…",
        )

    def check_updates(self, *_):
        try:
            if not Gio.AppInfo.launch_default_for_uri(RELEASES_URL, None):
                raise RuntimeError("The desktop could not open GitHub Releases.")
        except Exception as exc:
            self.toast("Could not open updates: " + str(exc), 6)
        else:
            self.toast("Opened Accented Releases.")

    def show_what_changes(self, *_):
        dialog = Adw.AlertDialog(
            heading="What Accented changes",
            body=(
                "Accented writes only accent-specific values to your user GTK 3 and GTK 4 CSS. "
                "Existing CSS is preserved and each change is backed up.\n\n"
                "“Match GNOME Desktop” uses GNOME’s nearest built-in accent, so it is an "
                "approximation rather than your exact hex color.\n\n"
                "Flatpak, Qt, Electron, and custom-drawn apps may not follow GTK user CSS. "
                "Reopen affected apps after Apply or Restore."
            ),
        )
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        dialog.present(self.window)

    def show_about(self, *_):
        dialog = Adw.AboutDialog(
            application_name="Accented",
            application_icon=APP_ID,
            version=__version__,
            developer_name="loew",
            comments="Pick a pixel. Make it your accent.",
            website="https://github.com/lrnolivia/Accented",
        )
        dialog.present(self.window)

    def close_requested(self, *_):
        if self.busy:
            self.message("A change is in progress. Accented will stay open until it finishes.", error=True)
            return True
        return False
