# Accented

Pick a pixel. Make it your accent.

A small native GTK 4 / libadwaita utility for GNOME on Bazzite, using GameBridge
Lite's centered composition.

The primary window is deliberately small: choose/type a color, choose from the native
dialog or pick a pixel from screen, optionally reopen Recent colors, then Apply Accent.
The large swatch is the preview.

Secondary controls live in the native hamburger:
- Match GNOME Desktop: nearest built-in GNOME accent, not exact Shell color.
- Restore Original Accent: removes only Accented-owned changes.
- Check for Updates: opens the public GitHub Releases page.
- What Changes and About: coverage and version information.

Accented writes only accent-specific values to user GTK 3/GTK 4 CSS, preserves unrelated
CSS, backs up changes, and supports Bazzite's root-owned /home -> /var/home layout.
It does not change fonts, padding, wallpaper, shell theme, or application layout.

For now updates remain explicit. Accented does not silently fetch or execute remote
installers. True unattended updates should be delegated to Flatpak/GNOME Software once
the app is packaged as a Flatpak.

Terminal recovery:
```sh
"$HOME/.local/bin/accented" --doctor
"$HOME/.local/bin/accented" --restore
"$HOME/.local/bin/accented" --uninstall
```
