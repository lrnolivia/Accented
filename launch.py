#!/usr/bin/python3
"""Launch the native app or perform explicit recovery from a terminal."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    if "--version" in sys.argv:
        from accented import __version__
        print("Accented " + __version__)
        return 0
    if "--uninstall" in sys.argv and (Path(__file__).resolve().parent / '.package-managed').exists():
        print('This installation is managed by your package manager. Use --restore first if you want to restore your previous accent, then remove the accented package with your system package manager. User backups are retained.')
        return 0
    if "--help" in sys.argv:
        print("Accented: choose a color, preview, then Apply.\n"
              "--version   Print version\n--doctor    Check desktop dependencies\n"
              "--restore   Restore Accented-owned changes without opening a window\n"
              "--uninstall Restore accents and remove the app; retain safety backups")
        return 0
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw, GLib
        if Gtk.get_major_version() != 4 or Gtk.get_minor_version() < 10:
            raise RuntimeError("GTK 4.10 or newer is required.")
    except (ImportError, ValueError, RuntimeError) as exc:
        print("Accented needs the system Python GTK 4 and libadwaita bindings.\n"
              "On Bazzite GNOME, launch from the host desktop, not a Distrobox or Flatpak terminal.\n"
              f"Details: {exc}", file=sys.stderr)
        return 1
    from accented.desktop import GnomeSettings
    from accented.core import AccentStore
    settings = GnomeSettings()
    from accented.environment import storage_paths, is_flatpak
    config,state=storage_paths(GLib.get_user_config_dir(),GLib.get_user_state_dir())
    store = AccentStore(config,state,settings)
    if "--doctor" in sys.argv:
        print(json.dumps({"app": "Accented", "gtk": f"4.{Gtk.get_minor_version()}",
            "adwaita": f"{Adw.get_major_version()}.{Adw.get_minor_version()}",
            "session": os.environ.get("XDG_SESSION_TYPE", "unknown"),
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
            "native_accent_available": settings.available, "flatpak": is_flatpak(),
            "gtk_config": str(store.config), "backups": str(store.root / "backups"),
            "interrupted_change": store.journal.exists()}, indent=2))
        return 0
    if "--uninstall" in sys.argv:
        from install import uninstall
        return uninstall(store)
    if "--restore" in sys.argv:
        try:
            print(store.restore()[1])
        except Exception as exc:
            print("Restore stopped: " + str(exc), file=sys.stderr)
            return 1
        return 0
    from accented.ui import Accented
    return Accented().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
