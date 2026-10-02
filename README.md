# Accented

Pick a pixel. Make it your accent.

A small native GTK 4 / libadwaita utility for GNOME on Bazzite. Its single-window
composition comes from GameBridge Lite. No webview or replacement desktop theme.

## Install and open

Save the provided `Accented-0.1.0.run` installer and run it with `bash` from your
normal Bazzite GNOME host terminal. Do not use sudo. No package layering, root
writes, pip installs, service, autostart, or broad Flatpak permission changes.

Alternatively, from this source directory:

```sh
/usr/bin/python3 install.py
"$HOME/.local/bin/accented"
```

Requirements: system Python 3.10+, PyGObject, GTK 4.10+, libadwaita 1.x.
Screen picking needs the desktop's `org.freedesktop.portal.Screenshot.PickColor`
portal. The chooser and hex input still work when the portal is unavailable.

## Use

Choose Color opens GTK's native color dialog. Pick from Screen hides Accented
briefly so the wallpaper is accessible, then asks the desktop to select one
pixel. Escape cancels the desktop picker. A 120-second timeout returns the app
when no response arrives. No screenshot is stored.

A valid hex entry updates only the preview. Copy puts the hex value on the
clipboard. Apply Accent backs up and updates the accent-specific sections of
your user GTK 3 and GTK 4 CSS. Recent colors are the last eight applied colors.
Restore removes only Accented's owned sections and restores an owned desktop
match when it has not been changed elsewhere.

The optional desktop match chooses the nearest GNOME preset using Oklab color
distance. It is approximate, not an arbitrary GNOME Shell color. It adds no new
swatches to GNOME Settings. Turning the option off and applying restores the
previous desktop preference if Accented still owns it.

## Coverage and safety

The exact accent is for GTK apps that honor user CSS. Reopen affected apps after
Apply or Restore. Sandboxed Flatpak, Qt, Electron, and custom-drawn applications
are not guaranteed to follow it. GNOME Settings itself can continue to display
only its built-in preset. This is not a full-desktop recoloring engine.

Existing CSS outside Accented's marked section is preserved byte-for-byte.
Symbolic links, malformed ownership records, conflicting edits, and concurrent
Accented writes stop the operation. Backups and the interrupted-write journal
live under `$XDG_STATE_HOME/accented` (normally `~/.local/state/accented`).

GTK 4.16+ accent variables allow modern libadwaita apps to derive appropriate
light/dark accent text. For older GTK apps, reapply after changing light/dark
appearance to refresh their legacy accent-text color. High-contrast mode keeps
native preview controls rather than forcing the custom preview style.

Only accents change. No font, padding, wallpaper, shell theme, or application
layout is changed by Apply. Installing or merely opening Accented applies nothing.

## Terminal recovery and uninstall

```sh
"$HOME/.local/bin/accented" --doctor
"$HOME/.local/bin/accented" --restore
"$HOME/.local/bin/accented" --uninstall
```

Close the app before uninstalling. Uninstall restores owned accents first; an
unresolved conflict stops removal. Backups are retained. The installer also
refuses to overwrite unrelated files or edited app files.

## Source verification

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q accented launch.py install.py
```

Native integration and visual verification require a working GTK 4 session;
headless unit tests do not prove behavior on your GNOME compositor.
