"""GNOME settings and the consent-mediated Wayland/X11 pixel picker."""
from __future__ import annotations
import uuid
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib
from .core import PRESETS, from_rgb


class GnomeSettings:
    def __init__(self):
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.gnome.desktop.interface", True) if source else None
        self.interface = Gio.Settings.new_full(schema, None, None) if schema else None
        self.available = bool(schema and schema.has_key("accent-color"))

    @property
    def dark(self):
        return bool(self.interface and self.interface.get_string("color-scheme") == "prefer-dark")

    def snapshot(self):
        if not self.available:
            raise RuntimeError("This GNOME session does not expose a native accent preference.")
        value = self.interface.get_user_value("accent-color")
        return {"user_value": value.unpack() if value is not None else None}

    def restore(self, snapshot):
        if not self.available or not self.interface.is_writable("accent-color"):
            raise RuntimeError("The native GNOME accent preference is not writable.")
        value = snapshot["user_value"]
        if value is None:
            self.interface.reset("accent-color")
        elif value in PRESETS:
            if not self.interface.set_string("accent-color", value):
                raise RuntimeError("GNOME rejected the requested accent preset.")
        else:
            raise ValueError("Unknown GNOME accent preset.")
        Gio.Settings.sync()
        if self.snapshot() != snapshot:
            raise RuntimeError("GNOME accent verification failed; recovery is required.")


class PixelPicker:
    """One request, subscribed before dispatch. Never saves a screen capture."""
    BUS = "org.freedesktop.portal.Desktop"
    PATH = "/org/freedesktop/portal/desktop"
    REQUEST = "org.freedesktop.portal.Request"

    def __init__(self, callback):
        self.callback = callback
        self.bus = None
        self.subscription = 0
        self.timeout = 0
        self.handle = None
        self.done = False
        self.early = {}
        self.replied = False

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            token = "accented_" + uuid.uuid4().hex
            sender = self.bus.get_unique_name()[1:].replace(".", "_")
            self.prefix = self.PATH + "/request/" + sender + "/"
            self.handle = self.prefix + token
            self.subscription = self.bus.signal_subscribe(
                self.BUS, self.REQUEST, "Response", None, None,
                Gio.DBusSignalFlags.NONE, self._response)
            self.timeout = GLib.timeout_add_seconds(120, self._expired)
            self.bus.call(self.BUS, self.PATH, "org.freedesktop.portal.Screenshot",
                          "PickColor", GLib.Variant("(sa{sv})", ("", {
                              "handle_token": GLib.Variant("s", token)})),
                          GLib.VariantType.new("(o)"), Gio.DBusCallFlags.NONE,
                          15000, None, self._called)
        except Exception as exc:
            self._finish(None, f"The desktop picker is unavailable: {exc}")
        return False

    def _called(self, bus, result):
        try:
            handle = bus.call_finish(result).unpack()[0]
            if self.done:
                self._close(handle)
                return
            self.handle = handle
            self.replied = True
            if handle in self.early:
                self._consume(self.early[handle])
            self.early.clear()
        except GLib.Error as exc:
            self._finish(None, f"The desktop picker could not start: {exc.message}")

    def _response(self, _bus, _sender, path, _interface, _signal, parameters):
        if self.done:
            return
        if path == self.handle:
            self._consume(parameters)
        elif not self.replied and path.startswith(self.prefix) and len(self.early) < 8:
            self.early[path] = parameters

    def _consume(self, parameters):
        try:
            response, results = parameters.unpack()
            if response == 1:
                self._finish(None, "Picking cancelled. Nothing was changed.")
            elif response != 0:
                self._finish(None, "The desktop could not pick that pixel.")
            else:
                self._finish(from_rgb(results["color"]), None)
        except (KeyError, TypeError, ValueError) as exc:
            self._finish(None, f"The picker returned an invalid color: {exc}")

    def _close(self, handle):
        if self.bus and handle:
            self.bus.call(self.BUS, handle, self.REQUEST, "Close", None, None,
                          Gio.DBusCallFlags.NONE, 3000, None, self._closed)

    @staticmethod
    def _closed(bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error:
            pass  # Request may already have ended or failed to start.

    def cancel(self):
        if not self.done:
            self._close(self.handle)
            self._finish(None, "Picking cancelled. Nothing was changed.")

    def _expired(self):
        self.timeout = 0
        self._close(self.handle)
        self._finish(None, "The picker timed out. Nothing was changed.")
        return False

    def _finish(self, color, message):
        if self.done:
            return
        self.done = True
        if self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
            self.subscription = 0
        if self.timeout:
            GLib.source_remove(self.timeout)
            self.timeout = 0
        self.early.clear()
        self.callback(color, message)
