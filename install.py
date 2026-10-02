#!/usr/bin/python3
"""User-only installation with ownership checks, rollback, and safe uninstall."""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from accented import __version__

APP_ID = "com.loew.accented"
PACKAGE_FILES = (
    "launch.py", "install.py", "accented/__init__.py", "accented/core.py",
    "accented/desktop.py", "accented/update.py", "accented/ui.py", "assets/com.loew.accented.png",
    "README.md", "LICENSE", "NOTICE", "PRODUCT.md", "DESIGN.md",
)
MARKER = ".accented-install.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    uid = os.geteuid()
    for part in (path, *path.parents):
        if not part.is_symlink():
            continue
        # A symlink at the path we are about to read/write is never safe.
        # Ancestor symlinks owned by another user are treated as system layout
        # (for example Bazzite's root-owned /home -> /var/home mapping).
        # User-owned ancestor symlinks remain blocked.
        if part == path or os.lstat(part).st_uid == uid:
            raise RuntimeError(f"Refusing a symbolic link: {part}")


def read(path):
    safe_path(path)
    if path.exists() and not path.is_file():
        raise RuntimeError(f"Not a regular file: {path}")
    return path.read_bytes() if path.exists() else None


def write(path, raw, mode=0o644):
    safe_path(path)
    if raw is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".accented-", dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), mode)
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):os.unlink(name)


def locations(home=None, data=None):
    home = Path(home or Path.home()).absolute()
    data = Path(data or os.environ.get('XDG_DATA_HOME', home/'.local/share')).absolute()
    dest = data/'accented'
    outside = {
        "launcher": home/'.local/bin/accented',
        "desktop": data/'applications'/f'{APP_ID}.desktop',
        "icon": data/'icons/hicolor/512x512/apps'/f'{APP_ID}.png',
    }
    return dest, outside


def marker(dest):
    raw = read(dest/MARKER)
    if raw is None:
        if dest.exists():raise RuntimeError(f"{dest} is not an Accented-owned install; left untouched.")
        return None
    result = json.loads(raw)
    if result.get('schema') != 1 or result.get('app_id') != APP_ID:
        raise RuntimeError('Unrecognized install record; no files changed.')
    if set(result['files']) != set(PACKAGE_FILES) or set(result['external']) != {'launcher','desktop','icon'}:
        raise RuntimeError('Unexpected paths in install record; no files changed.')
    return result


def verify_owned(dest, outside, previous):
    if previous:
        for name, expected in previous['files'].items():
            raw = read(dest/name)
            if raw is None or digest(raw) != expected:
                raise RuntimeError(f'Installed file was edited or removed: {dest/name}. Nothing overwritten.')
        for path in dest.rglob('*'):
            safe_path(path)
            relative = path.relative_to(dest)
            if path.is_file() and str(relative) not in PACKAGE_FILES and str(relative) != MARKER and '__pycache__' not in relative.parts:
                raise RuntimeError(f'Unexpected file in app folder: {relative}. Left untouched.')
    for kind, path in outside.items():
        raw = read(path)
        expected = previous['external'][kind] if previous else None
        if raw is not None and (expected is None or digest(raw) != expected):
            raise RuntimeError(f'Another file occupies {path}. Nothing overwritten.')


def refresh(outside):
    for args in (['update-desktop-database', str(outside['desktop'].parent)],):
        if shutil.which(args[0]):
            subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)


@contextlib.contextmanager
def install_lock(parent):
    safe_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    path = parent/'.accented-install.lock'
    safe_path(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def install(source, home=None, data=None):
    source = Path(source).absolute()
    dest, outside = locations(home,data)
    for path in (dest,*outside.values()):safe_path(path)
    payload = {name: read(source/name) for name in PACKAGE_FILES}
    if any(value is None for value in payload.values()):
        raise RuntimeError('Incomplete package; no files installed.')
    launcher = ('#!/bin/sh\nexec /usr/bin/python3 -I ' + shlex.quote(str(dest/'launch.py')) + ' "$@"\n').encode()
    # Desktop Exec quoting is not shell quoting.
    execpath = str(outside['launcher']).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    desktop = (f'[Desktop Entry]\nType=Application\nName=Accented\n'
        'Comment=Pick a pixel. Make it your accent.\n'
        f'Exec="{execpath}"\nIcon={APP_ID}\nTerminal=false\n'
        'Categories=Settings;DesktopSettings;GTK;\nKeywords=color;accent;picker;eyedropper;\n'
        'StartupNotify=true\n').encode()
    external = {'launcher':launcher,'desktop':desktop,'icon':payload['assets/com.loew.accented.png']}
    manifest = {'schema':1,'app_id':APP_ID,'version':__version__,
        'files':{name:digest(raw) for name,raw in payload.items()},
        'external':{name:digest(raw) for name,raw in external.items()}}
    with install_lock(dest.parent):
        previous = marker(dest)
        verify_owned(dest,outside,previous)
        oldoutside = {kind: read(path) for kind,path in outside.items()}
        stage = Path(tempfile.mkdtemp(prefix='.accented-new-',dir=dest.parent))
        previous_dir = None
        placed = False
        try:
            for name,raw in payload.items():write(stage/name,raw)
            write(stage/MARKER,json.dumps(manifest,indent=2).encode())
            if dest.exists():
                previous_dir = Path(tempfile.mkdtemp(prefix='.accented-old-',dir=dest.parent))
                previous_dir.rmdir();dest.rename(previous_dir)
            stage.rename(dest);placed=True
            for kind,raw in external.items():write(outside[kind],raw,0o755 if kind=='launcher' else 0o644)
        except Exception:
            for kind,raw in oldoutside.items():write(outside[kind],raw,0o755 if kind=='launcher' else 0o644)
            if placed:shutil.rmtree(dest)
            if previous_dir and previous_dir.exists():previous_dir.rename(dest)
            raise
        finally:
            if stage.exists():shutil.rmtree(stage)
        if previous_dir and previous_dir.exists():shutil.rmtree(previous_dir)
    refresh(outside)
    return outside['launcher']


def uninstall(store, home=None, data=None):
    dest, outside = locations(home,data)
    try:
        with install_lock(dest.parent):
            previous = marker(dest)
            if previous is None:
                print('Accented is not installed at this location.')
                return 0
            verify_owned(dest,outside,previous)
            # Restore before deleting the app. Conflicts stop uninstall safely.
            print(store.restore()[1])
            for kind,path in outside.items():
                raw = read(path)
                if raw is not None and digest(raw) == previous['external'][kind]:path.unlink()
            shutil.rmtree(dest)
        refresh(outside)
    except Exception as exc:
        print('Uninstall stopped: '+str(exc),file=sys.stderr)
        return 1
    print('Accented removed. Your accent backups were kept.')
    return 0


def dependencies():
    result = subprocess.run(['/usr/bin/python3','-c',
        'import gi;gi.require_version("Gtk","4.0");gi.require_version("Adw","1");'
        'from gi.repository import Gtk,Adw;assert Gtk.get_minor_version()>=10,"GTK 4.10+ required"'],
        capture_output=True,text=True,timeout=15)
    if result.returncode:
        raise RuntimeError('System GTK 4.10+ / libadwaita Python bindings are unavailable. '
            'Run from the Bazzite GNOME host terminal, not a container. No system packages were changed.\n'+result.stderr.strip())


def main():
    try:
        dependencies()
        if '--check' in sys.argv:
            print('Accented dependencies are ready. Nothing installed.')
            return 0
        if os.geteuid()==0:
            raise RuntimeError('Run this installer as your normal desktop user, without sudo.')
        launcher=install(Path(__file__).resolve().parent)
        print('Accented installed. No accent has been applied yet.\nOpen Accented from the app grid, or run:\n'+shlex.quote(str(launcher)))
        return 0
    except Exception as exc:
        print('Installation stopped: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
