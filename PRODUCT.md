# Accented

A small color picker for custom GTK app accents, optimized for Bazzite GNOME.
The primary flow is choose/pick/type, then Apply.

Exact custom color applies to supported GTK application styles. Optional GNOME desktop
matching is approximate and limited to built-in presets.

The interface is native GTK 4/libadwaita and preserves GameBridge Lite's centered,
single-panel composition. Secondary functions live in the native hamburger menu.

Installation and settings changes stay in the user's home. Apply is backed up,
conflict-guarded and recoverable. Update navigation opens the public GitHub Releases
page; Accented does not silently execute remote installers.

Flatpak candidate: exact GTK accent changes use narrowly scoped host GTK configuration and shared Accented recovery state. The sandbox intentionally does not write GNOME Shell settings or execute host commands. Flatpak owns application updates/removal. Native and Flatpak ownership records remain interoperable; a native Shell change must be restored by the native edition before migration.
