"""Exercise the real D-Bus picker client against an isolated protocol fixture.

Run with dbus-run-session. This does not prove a real compositor's pixel UI.
"""
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib
from accented.desktop import PixelPicker

XML = '''<node>
<interface name="org.freedesktop.portal.Screenshot">
<method name="PickColor"><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="o" direction="out"/></method>
</interface>
<interface name="org.freedesktop.portal.Request"><method name="Close"/></interface>
</node>'''
info = Gio.DBusNodeInfo.new_for_xml(XML)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
mode = "success"
closed = []
registered = []
acquired = []


def tick(seconds=.08):
    end = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < end:
        while context.pending(): context.iteration(False)
        time.sleep(.002)


def close_request(_connection, _sender, path, _interface, _method, _args, invocation):
    closed.append(path)
    invocation.return_value(None)


def pick(connection, sender, _path, _interface, method, parameters, invocation):
    assert method == "PickColor"
    parent, options = parameters.unpack()
    assert parent == "" and options['handle_token'].startswith('accented_')
    if mode == "unavailable":
        invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", "Picker is not supported")
        return
    handle = PixelPicker.PATH + '/request/' + sender[1:].replace('.', '_') + '/' + options['handle_token']
    if mode == "alternative": handle += '_alternate'
    registered.append(connection.register_object(handle, info.interfaces[1], close_request, None, None))
    results = {'color': GLib.Variant('(ddd)', (18/255, 171/255, 239/255))}
    code = 0
    if mode == "cancelled": code, results = 1, {}
    elif mode == "failed": code, results = 2, {}
    elif mode == "malformed": results = {'color': GLib.Variant('(ddd)', (float('nan'), 0, 0))}
    def respond():
        connection.emit_signal(sender, handle, PixelPicker.REQUEST, 'Response', GLib.Variant('(ua{sv})', (code, results)))
        return False
    if mode in ('early', 'alternative'): respond()
    invocation.return_value(GLib.Variant('(o)', (handle,)))
    if mode not in ('hold', 'early', 'alternative'): GLib.idle_add(respond)


registration = bus.register_object(PixelPicker.PATH, info.interfaces[0], pick, None, None)
ownership = Gio.bus_own_name_on_connection(bus, PixelPicker.BUS, Gio.BusNameOwnerFlags.NONE,
                                          lambda *_: acquired.append(True), lambda *_: None)
tick()
assert acquired, 'Could not own isolated fixture portal name'
for mode in ('success', 'early', 'alternative', 'cancelled', 'failed', 'malformed', 'unavailable', 'timeout', 'cancel'):
    test_mode = mode
    if mode in ('timeout', 'cancel'): mode = 'hold'
    events = []
    picker = PixelPicker(lambda color, message: events.append((color, message)))
    picker.start(); tick()
    if test_mode == 'timeout': picker._expired()
    if test_mode == 'cancel': picker.cancel()
    tick()
    assert len(events) == 1, (test_mode, events)
    color, message = events[0]
    if test_mode in ('success', 'early', 'alternative'):
        assert color == '#12ABEF' and message is None, (test_mode, events)
    else:
        assert color is None and message, (test_mode, events)
    assert picker.done and picker.subscription == 0 and picker.timeout == 0
    picker.cancel(); tick(.02)
    assert len(events) == 1, 'Duplicate callback after completion'
    print('PORTAL_PASS', test_mode)
for identifier in registered: bus.unregister_object(identifier)
bus.unregister_object(registration)
Gio.bus_unown_name(ownership)
print('PORTAL_PROTOCOL_PASS: 9 cases; real GNOME screen acquisition remains environment-specific')
