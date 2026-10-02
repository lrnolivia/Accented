# Accented

Pick a pixel. Make it your accent.

A small native GTK 4 / libadwaita utility for GNOME on Bazzite. Its centered
single-window composition comes from GameBridge Lite. No webview or replacement
desktop theme.

## Install and open

Save the provided `Accented-0.2.0.run` installer and run it with `bash` from
your normal Bazzite GNOME host terminal. Do not use sudo. No package layering,
root writes, pip installs, service, autostart, or broad Flatpak permission changes.

Alternatively, from this source directory:

```sh
/usr/bin/python3 install.py
"$HOME/.local/bin/accented"
```

Requirements: system Python 3.10+, PyGObject, GTK 4.10+, libadwaita 1.x.
Screen picking needs the desktop's `org.freedesktop.portal.Screenshot.PickColor`
portal. The chooser and hex input still work when the portal is unavailable.

## Use

The main window is deliberately small: choose or type a color, optionally reopen
Recent colors, then Apply Accent. The large swatch is the preview. Choose Color
opens GTK's native color dialog. Pick from Screen hides Accented briefly, then asks
the desktop to select one pixel. Escape cancels; no screenshot is stored.

Secondary controls live in the native header-bar menu:
- Match GNOME Desktop uses the nearest GNOME preset, not an exact custom Shell color.
- Restore Original Accent removes only Accented-owned accent changes.
- Automatically Update checks on launch and installs a newer verified user-level build.
- Check for Updates performs the same check manually.
- What Changes and About explain coverage and version information.

## Updates

Accented's updater downloads a small HTTPS manifest and accepts installers only
from the dedicated Accented update feed. The installer SHA-256 must match the
manifest before anything executes. Updates run through the same guarded, user-only
installer as the original installation. No root updater, service, timer, daemon, or
telemetry is installed.

Automatic updates are enabled by default and can be disabled from the hamburger
menu. A failed automatic check is silent; a manual check reports the error. After
a successful update, Accented offers to restart into the new version.

## Coverage and safety

The exact accent is for GTK apps that honor user CSS. Reopen affected apps after
Apply or Restore. Sandboxed Flatpak, Qt, Electron, and custom-drawn applications
are not guaranteed to follow it. GNOME Settings itself can continue to display
only its built-in preset.

Existing CSS outside Accented's marked section is preserved byte-for-byte.
Symbolic links in user-controlled target paths, malformed ownership records,
conflicting edits, and concurrent Accented writes stop the operation. Bazzite's
root-owned `/home -> /var/home` system layout is supported. Backups and interrupted
write recovery live under `$XDG_STATE_HOME/accented`.

Only accents change. No font, padding, wallpaper, shell theme, or application
layout is changed by Apply. Installing or merely opening Accented applies nothing.

## Terminal recovery and uninstall

```sh
"$HOME/.local/bin/accented" --doctor
"$HOME/.local/bin/accented" --restore
"$HOME/.local/bin/accented" --uninstall
```

Close the app before uninstalling. Uninstall restores owned accents first; an
unresolved conflict stops removal. Backups are retained.

## Source verification

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q accented launch.py install.py
```

Native integration and visual verification require a working GTK 4 session;
headless unit tests do not prove behavior on your GNOME compositor.
