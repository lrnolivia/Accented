# Accented

A small color picker for custom GTK app accents, optimized for Bazzite GNOME.
The primary flow is intentionally short: choose/pick/type, then Apply.

The selected hex is exact for supported GTK application styles. Optional GNOME
desktop matching is explicitly approximate and limited to built-in presets. The
app must never describe that match as exact GNOME Shell support.

Installation and settings changes stay in the user's home. Selecting a color is
read-only. Apply is backed up, conflict guarded and recoverable.

Networking exists only for the updater. The app checks a dedicated HTTPS update
feed, verifies the installer checksum, and runs the same user-level guarded
installer. Automatic launch-time updates can be disabled, and a manual Check for
Updates command lives in the native hamburger menu. No updater daemon, service,
timer or telemetry is allowed.

The interface is a native GTK 4/libadwaita application, not a web rendering of
Adwaita. GameBridge Lite is the composition reference. The supplied Accented icon
is the app identity, not a GameBridge replacement.
