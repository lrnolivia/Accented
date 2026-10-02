# Accented

Pick a pixel. Make it your accent.

A small GTK desktop color utility for GNOME on Bazzite, derived from GameBridge Lite's compact GTK window, centered heading, cards, spacing and native light/dark behavior. GameBridge itself is not modified.

## Intended behavior

- Choose a custom color, enter a hex value, or pick one screen pixel through the desktop portal.
- Preview the color before applying anything.
- Apply an exact accent override to user-level GTK 3 and GTK 4 styles.
- Optionally match GNOME Shell to the nearest built-in accent. This is explicitly an approximation, not an arbitrary Shell color or a new swatch in GNOME Settings.
- Restore only changes owned by Accented. Preserve unrelated CSS and refuse conflicting or symlinked configuration rather than overwrite another theme tool.
- Keep settings, backups and installation in the user's home directory. No root, system-image changes, broad Flatpak permissions, or background service.

## Coverage

Native GTK applications that honor user CSS are the first target. Applications may need reopening. Sandboxed Flatpak applications, Qt/Electron applications, and custom-drawn interfaces are not promised to follow the exact accent. GNOME's built-in accent preference is an enum, not a hex color.

## Source

UI foundation: `lrnolivia/GameBridge`, commit `3606f651319891a094a1e80625ac36591be79f4c`, especially `lite/GameBridge-Lite.py`. The full 19-file source snapshot has been retrieved as a development reference. This repository is an independent app, not a GameBridge replacement.

This branch is under development. It is not a released or Bazzite-verified build.
