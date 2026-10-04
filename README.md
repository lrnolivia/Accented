## Native Linux packages

Download `.deb` (Debian 13 / Ubuntu with GTK 4.10+) or `.rpm` (Fedora-family GNOME) from [Releases](https://github.com/lrnolivia/Accented/releases/latest). Install with your graphical package manager or `sudo apt install ./accented_*.deb` / `sudo dnf install ./accented-*.rpm`.

The package manager owns application files under `/usr`; your accent preferences and safety backups stay in your home directory. Run `accented --restore` before removing the package if you want the previous accent restored. Removing the package does not silently change desktop preferences or delete backups.

Bazzite and other Atomic desktops: do not use `dnf install` on the host. An RPM may be layered with the distribution's supported rpm-ostree workflow, requiring a new deployment/reboot. This path has not yet been validated on a physical Bazzite system. A sandboxed Flatpak candidate now supports the GTK accent flow with narrowly scoped host configuration access; see below. Older `.run` releases are retained for rollback, but native packages are the primary downloads.

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

## Flatpak candidate

The review build uses GNOME Platform 50. Download the exact tested bundle from the Flatpak workflow artifact, verify its SHA256SUMS, then install with `flatpak install --user ./Accented-review.flatpak`. This is a review artifact, not a published Flathub listing or an automatic update feed.

The sandbox grants access only to `gtk-3.0`, `gtk-4.0`, and `~/.local/state/accented`. If you use a custom host XDG state directory, that exact Accented subdirectory needs an explicit Flatpak permission override; the application does not request broad home access or substitute a new ownership record. It has no network permission, unrestricted home access, host-command execution, or dconf write permission. Screen picking still uses the consent-mediated desktop portal. Native “Match GNOME Desktop” is unavailable in the Flatpak; compatible GTK applications receive the exact selected color.

Native and Flatpak editions share ownership records and a lock, so neither silently overwrites the other's accent block. If the native edition previously matched GNOME Shell, use its Restore action before switching to Flatpak. The sandbox fails closed rather than bypassing that recovery requirement. Keep backups when uninstalling; restore the accent first if desired.

Flatpak owns application updates and removal. “Check for Updates” opens the software manager in this edition. A manually downloaded bundle has no automatic feed unless a suitable repository is separately configured.

To build without weakening the sandbox:

```sh
flatpak-builder --user --install-deps-from=flathub --repo=flatpak-repo --force-clean build/flatpak packaging/flatpak/com.loew.accented.json
flatpak build-bundle --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo flatpak-repo Accented-review.flatpak com.loew.accented
```

Legacy `.run` installers remain available only for rollback. Prefer native packages or a verified Flatpak candidate.

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
