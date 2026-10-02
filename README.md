<p align="center">
  <img src="assets/com.loew.accented.png" width="96" alt="Accented icon">
</p>

# Accented

**Pick a pixel. Make it your accent.**

Accented is a small native GTK 4 / libadwaita utility for GNOME that lets you choose an exact custom GTK accent color, type a hex value, or pick one directly from your screen.

It was built for Bazzite GNOME, but should work on modern GNOME desktops with GTK 4.10+, libadwaita, PyGObject, and the desktop screenshot portal.

## What it does

- Pick any screen pixel through the desktop portal.
- Use the native GNOME color chooser or enter a hex color.
- Apply the exact color to GTK 3 and GTK 4 apps that honor user CSS.
- Optionally match GNOME Shell to the nearest built-in GNOME accent.
- Keep recent colors.
- Restore only the changes Accented owns.
- Preserve unrelated GTK CSS and keep recovery backups.
- Persist across reboots without a background service.

GNOME Shell only exposes its built-in accent presets. Accented therefore keeps your **exact** selected color for compatible GTK apps and can optionally use the nearest GNOME preset for the desktop shell.

## Install

Open the **Releases** page and download the newest `Accented-<version>.run` file:

https://github.com/lrnolivia/Accented/releases/latest

Then run it as your normal desktop user, **without sudo**:

```bash
chmod +x ~/Downloads/Accented-*.run
~/Downloads/Accented-*.run
```

The installer writes only to your user directories under `~/.local` and does not layer packages onto Bazzite.

Each release also includes `SHA256SUMS` if you want to verify the download first.

## Usage

1. Open **Accented** from the app grid.
2. Choose a color, enter a hex value, or select **Pick from Screen**.
3. Open the hamburger menu if you want **Match GNOME Desktop**.
4. Select **Apply Accent**.
5. Reopen apps that were already running if they do not refresh their GTK styling immediately.

GNOME's built-in desktop accent setting updates live. Accented does **not** restart GNOME Shell. On Wayland, GNOME Shell is the compositor, and force-restarting it would terminate the desktop session.

## Safety and recovery

Accented backs up every owned change and refuses to overwrite unexpected edits or user-controlled symbolic links.

Terminal recovery commands:

```bash
"$HOME/.local/bin/accented" --doctor
"$HOME/.local/bin/accented" --restore
"$HOME/.local/bin/accented" --uninstall
```

Backups are kept under `$XDG_STATE_HOME/accented` (normally `~/.local/state/accented`).

## Coverage

Exact custom accents apply to GTK applications that honor user CSS. Flatpak sandboxes, Qt, Electron, and custom-drawn interfaces may not follow those values.

The screen picker uses `org.freedesktop.portal.Screenshot.PickColor` and does not save a screenshot.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q accented launch.py install.py
```

The native UI smoke test runs under GTK/libadwaita in CI.

## License

GPL-3.0.
