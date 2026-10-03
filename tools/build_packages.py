#!/usr/bin/env python3
"""Build native packages; never install or edit the host desktop."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from accented import __version__


def stage(root):
    app = root / 'usr/share/accented'
    app.mkdir(parents=True)
    for name in ('accented', 'assets'):
        shutil.copytree(ROOT / name, app / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('launch.py', 'install.py', 'README.md', 'LICENSE', 'NOTICE', 'PRODUCT.md', 'DESIGN.md'):
        shutil.copy2(ROOT / name, app / name)
    (app / '.package-managed').write_text('Native package manager owns this installation.\n')
    binary = root / 'usr/bin/accented'
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/share/accented/launch.py "$@"\n')
    binary.chmod(0o755)
    desktop = root / 'usr/share/applications/com.loew.accented.desktop'
    desktop.parent.mkdir(parents=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Accented\nComment=Pick a pixel. Make it your accent.\nExec=accented\nIcon=com.loew.accented\nTerminal=false\nCategories=Settings;DesktopSettings;\nStartupNotify=true\n')
    icon = root / 'usr/share/icons/hicolor/512x512/apps/com.loew.accented.png'
    icon.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'assets/com.loew.accented.png', icon)
    for item in root.rglob('*'):
        if item.is_dir(): item.chmod(0o755)
        elif item != binary: item.chmod(0o644)


def build(kind, output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='accented-package-') as temp:
        work = Path(temp)
        payload = work / 'payload'
        stage(payload)
        if kind == 'deb':
            control = payload / 'DEBIAN/control'
            control.parent.mkdir()
            control.write_text(f'Package: accented\nVersion: {__version__}\nSection: utils\nPriority: optional\nArchitecture: all\nMaintainer: loew.fi\nDepends: python3, python3-gi, gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1, gsettings-desktop-schemas\nRecommends: xdg-desktop-portal-gnome\nHomepage: https://github.com/lrnolivia/Accented\nDescription: Native GNOME accent color utility\n Pick a color, preview it, and apply reversible desktop accent changes.\n')
            target = output / f'accented_{__version__}_all.deb'
            subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(payload), str(target)], check=True)
        else:
            top = work / 'rpmbuild'
            for name in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'): (top / name).mkdir(parents=True)
            spec = top / 'SPECS/accented.spec'
            spec.write_text(f'''Name: accented
Version: {__version__}
Release: 1
Summary: Native GNOME accent color utility
License: GPL-3.0-only
URL: https://github.com/lrnolivia/Accented
BuildArch: noarch
Requires: python3, python3-gobject, gtk4 >= 4.10, libadwaita, gsettings-desktop-schemas
Recommends: xdg-desktop-portal-gnome
%description
Pick a color, preview it, and apply reversible desktop accent changes.
%install
mkdir -p %{{buildroot}}
cp -a {payload}/usr %{{buildroot}}/
%files
/usr/bin/accented
/usr/share/accented
/usr/share/applications/com.loew.accented.desktop
/usr/share/icons/hicolor/512x512/apps/com.loew.accented.png
''')
            subprocess.run(['rpmbuild', '--define', f'_topdir {top}', '--define', '__os_install_post %{nil}', '-bb', str(spec)], check=True)
            built = list((top / 'RPMS').rglob('*.rpm'))
            if len(built) != 1: raise RuntimeError('Expected one RPM')
            target = output / built[0].name
            shutil.copy2(built[0], target)
        print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('format', choices=('deb', 'rpm'))
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    build(args.format, args.output.resolve())
