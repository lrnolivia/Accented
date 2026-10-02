# Accented

A small color picker for custom GTK app accents, optimized for Bazzite GNOME.
The primary flow is choose/pick/type, preview, Apply, and Restore.

The selected hex is exact for supported GTK application styles. The optional
GNOME desktop match is explicitly approximate and limited to built-in presets.
The app must never describe that match as exact GNOME Shell support.

Installation and settings changes stay in the user's home. Preview is read-only.
Apply is backed up, guarded against conflicts, and recoverable. No networking,
telemetry, background service, wallpaper changes, or theme replacement.

The interface is a native GTK 4/libadwaita application, not a web rendering of
Adwaita. GameBridge Lite is the composition reference. The supplied Accented icon
is the app identity, not a GameBridge replacement.
