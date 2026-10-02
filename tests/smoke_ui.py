"""Native GTK smoke/geometry/interaction test; run under an isolated display."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sandbox=tempfile.TemporaryDirectory(prefix='accented-ui-')
os.environ['XDG_CONFIG_HOME']=sandbox.name+'/config'
os.environ['XDG_STATE_HOME']=sandbox.name+'/state'
os.environ['GSETTINGS_BACKEND']='memory'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
from gi.repository import Adw, Gtk, GLib, Graphene
from accented.ui import Accented

def tick(seconds=.2):
    end=time.monotonic()+seconds
    context=GLib.MainContext.default()
    while time.monotonic()<end:
        while context.pending():context.iteration(False)
        time.sleep(.01)

def assert_visible_inside(widget,window):
    ok,bounds=widget.compute_bounds(window)
    assert ok
    assert bounds.get_x() >= -1 and bounds.get_y() >= -1
    assert bounds.get_x()+bounds.get_width() <= window.get_width()+1

app=Accented()
assert app.register(None)
app.activate();tick(.6)
assert app.window.get_visible()
for widget in (app.hero, app.panel):
    for edge in ('top','bottom','start','end'):
        assert getattr(widget,'get_margin_'+edge)()==24
assert app.hero_surface.has_css_class('accented-hero-surface')
assert app.controls_surface.has_css_class('accented-controls-surface')
assert Gtk.IconTheme.get_for_display(app.window.get_display()).has_icon('com.loew.accented')
assert app.hero.get_orientation()==Gtk.Orientation.HORIZONTAL
assert app.hero_icon.get_pixel_size()==96
assert app.header.has_css_class('accented-header')
assert app.header.has_css_class('flat')
assert app.entry.get_text()=='#3584E4'
assert app.apply_button.get_sensitive()
assert not app.restore_action.get_enabled()
assert app.menu_button.get_menu_model() is not None
assert not hasattr(app,'scroll')
assert not hasattr(app,'status')
assert not hasattr(app,'spinner')
assert not app.store.config.exists()
assert not app.recent_expander.get_visible()

app.entry.set_text('bad!');tick()
assert not app.apply_button.get_sensitive()
assert app.validation.get_visible()
app.entry.set_text('#db805a');tick()
assert app.color=='#DB805A'
assert not app.store.config.exists()

app.apply();tick(.8)
assert app.store.state()['color']=='#DB805A'
assert app.restore_action.get_enabled()
assert app.recent_expander.get_visible()
app.restore();tick(.8)
assert not app.store.state().get('files')

with patch('accented.ui.Gio.AppInfo.launch_default_for_uri', return_value=True) as launch:
    app.check_updates();tick()
    launch.assert_called_once()

for appearance in (Adw.ColorScheme.FORCE_LIGHT,Adw.ColorScheme.FORCE_DARK):
    app.style.set_color_scheme(appearance);tick(.3)
    for width in (560,380):
        app.window.set_default_size(width,650);tick(.3)
        for widget in (app.panel,app.entry,app.apply_button,app.menu_button,app.picker_actions):
            assert_visible_inside(widget,app.window)

app.choose_color();tick(.3)
assert app.dialog is not None
for window in Gtk.Window.get_toplevels():
    if window is not app.window:window.close()
tick(.3)
print('NATIVE_UI_PASS',flush=True)
if '--capture' in sys.argv:
    app.window.set_default_size(560,440);tick(10)
    width,height=app.window.get_width(),app.window.get_height()
    paint=Gtk.WidgetPaintable.new(app.window);snapshot=Gtk.Snapshot()
    paint.snapshot(snapshot,width,height);node=snapshot.to_node()
    assert node is not None
    rect=Graphene.Rect();rect.init(0,0,width,height)
    texture=app.window.get_native().get_renderer().render_texture(node,rect)
    Path('evidence').mkdir(exist_ok=True)
    assert texture.save_to_png('evidence/Accented-dark.png')
    print('CAPTURE_READY',flush=True)
    tick(15)
app.window.close();tick()
sandbox.cleanup()
