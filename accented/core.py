"""Color math and guarded, user-level CSS transactions. No GTK dependency."""
from __future__ import annotations

import base64
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

PRESETS = {
    "blue": "#3584E4", "teal": "#2190A4", "green": "#3A944A",
    "yellow": "#C88800", "orange": "#ED5B00", "red": "#E62D42",
    "pink": "#D56199", "purple": "#9141AC", "slate": "#6F8396",
}
BEGIN = "/* Accented managed accent: begin */"
END = "/* Accented managed accent: end */"
TARGETS = ("gtk-3.0/gtk.css", "gtk-4.0/gtk.css")


class ConflictError(RuntimeError):
    """An external change or unsafe path needs attention before a write."""


def normalize_hex(value: str) -> str:
    value = value.strip().removeprefix("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", value):
        value = "".join(c * 2 for c in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Enter a color such as #DB805A or #DA8.")
    return "#" + value.upper()


def rgb(value: str) -> tuple[float, float, float]:
    value = normalize_hex(value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def from_rgb(values) -> str:
    values = tuple(values)
    if len(values) != 3 or not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
        raise ValueError("The desktop returned an invalid sRGB color.")
    return "#" + "".join(f"{int(v * 255 + 0.5):02X}" for v in values)


def linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(value: str) -> float:
    return sum(w * linear(c) for w, c in zip((0.2126, 0.7152, 0.0722), rgb(value)))


def contrast(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def foreground(value: str) -> str:
    return max(("#000000", "#FFFFFF"), key=lambda candidate: contrast(value, candidate))


def standalone(value: str, dark: bool) -> str:
    """Keep hue while making classic GTK accent text readable on neutral surfaces."""
    background = "#242424" if dark else "#FFFFFF"
    destination = 1.0 if dark else 0.0
    channels = rgb(value)
    for step in range(101):
        amount = step / 100
        result = from_rgb(c * (1 - amount) + destination * amount for c in channels)
        if contrast(result, background) >= 4.5:
            return result
    return "#FFFFFF" if dark else "#000000"


def oklab(value: str) -> tuple[float, float, float]:
    r, g, b = map(linear, rgb(value))
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            0.0259040371*l + 0.7827717662*m - 0.8086757660*s)


def nearest_preset(value: str) -> str:
    point = oklab(value)
    return min(PRESETS, key=lambda name: sum((a-b)**2 for a, b in zip(point, oklab(PRESETS[name]))))


def accent_css(value: str, *, modern: bool, dark: bool = False) -> str:
    value = normalize_hex(value)
    text = foreground(value)
    result = (f"@define-color accent_bg_color {value};\n"
              f"@define-color accent_fg_color {text};\n"
              f"@define-color accent_color {standalone(value, dark)};\n"
              f"@define-color theme_selected_bg_color {value};\n"
              f"@define-color theme_selected_fg_color {text};\n")
    if modern:
        result += (":root {\n"
                   f"  --accent-bg-color: {value};\n"
                   f"  --accent-fg-color: {text};\n"
                   "}\n")
    return "\n" + BEGIN + "\n" + result + END + "\n"


def _encode(raw: bytes | None) -> str | None:
    return None if raw is None else base64.b64encode(raw).decode("ascii")


def _decode(raw: str | None) -> bytes | None:
    return None if raw is None else base64.b64decode(raw, validate=True)


def _check_path(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ConflictError(f"Refusing a symlinked configuration path: {candidate}")
    if path.exists() and not path.is_file():
        raise ConflictError(f"Not a regular file: {path}")


def _read(path: Path) -> bytes | None:
    _check_path(path)
    return path.read_bytes() if path.exists() else None


def _write(path: Path, raw: bytes | None) -> None:
    _check_path(path)
    if raw is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".accented-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _json(raw: bytes | None, fallback):
    return json.loads(raw) if raw is not None else fallback


class AccentStore:
    """A single-writer transaction manager. Settings adapter is optional for tests."""
    def __init__(self, config: Path, state: Path, settings=None):
        self.config = config.absolute()
        self.root = state.absolute() / "accented"
        self.settings = settings
        self.state_file = self.root / "state.json"
        self.journal = self.root / "pending.json"

    def state(self) -> dict:
        value = _json(_read(self.state_file), {})
        if value and value.get("schema") != 1:
            raise ConflictError("Unknown Accented state version; no settings were changed.")
        return value

    @contextlib.contextmanager
    def _lock(self):
        _check_path(self.root / "lock")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ConflictError("Another Accented change is in progress.") from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _unmanaged(self, raw: bytes | None, known: dict | None) -> bytes | None:
        text = (raw or b"").decode("utf-8")
        if not known:
            if BEGIN in text or END in text:
                raise ConflictError("Found an accent block without matching ownership data.")
            return raw
        block = known["block"]
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.count(block) != 1:
            raise ConflictError("Accented's CSS was changed elsewhere. Restore was not forced.")
        clean = text.replace(block, "", 1).encode("utf-8")
        return None if clean == b"" and known["original_missing"] else clean

    def _transaction(self, changes: dict[str, bytes | None], new_state: dict,
                     shell_before=None, shell_after=None, change_shell=False) -> Path:
        before = {name: _encode(_read(self.config / name)) for name in changes}
        after = {name: _encode(raw) for name, raw in changes.items()}
        old_state = _read(self.state_file)
        journal = {"schema": 1, "before": before, "after": after,
                   "state_before": _encode(old_state), "state_after": new_state,
                   "shell_before": shell_before, "shell_after": shell_after,
                   "change_shell": change_shell}
        backup = self.root / "backups" / uuid.uuid4().hex
        backup.mkdir(parents=True, mode=0o700)
        data = json.dumps(journal, indent=2).encode()
        _write(backup / "transaction.json", data)
        _write(self.journal, data)
        try:
            # Recheck after making the backup, before touching any configuration.
            for name, expected in before.items():
                if _read(self.config / name) != _decode(expected):
                    raise ConflictError(f"Configuration changed during Apply: {name}")
            if change_shell and self.settings.snapshot() != shell_before:
                raise ConflictError("GNOME's accent changed during Apply.")
            for name, raw in changes.items():
                _write(self.config / name, raw)
            if change_shell:
                self.settings.restore(shell_after)
            _write(self.state_file, json.dumps(new_state, indent=2).encode())
        except Exception:
            # Recovery refuses unexpected concurrent changes rather than erasing them.
            self._recover()
            raise
        self.journal.unlink()
        return backup

    def _recover(self) -> bool:
        journal = _json(_read(self.journal), None)
        if journal is None:
            return False
        if journal.get("schema") != 1 or set(journal["before"]) != set(journal["after"]):
            raise ConflictError("Unknown recovery journal; inspect the backup before continuing.")
        if not set(journal["before"]).issubset(TARGETS):
            raise ConflictError("Unexpected path in recovery journal.")
        for name in journal["before"]:
            current = _read(self.config / name)
            if current not in (_decode(journal["before"][name]), _decode(journal["after"][name])):
                raise ConflictError(f"Recovery found newer edits in {name}; backup retained.")
        if journal["change_shell"]:
            if self.settings is None or not self.settings.available:
                raise ConflictError("GNOME settings are unavailable for recovery.")
            if self.settings.snapshot() not in (journal["shell_before"], journal["shell_after"]):
                raise ConflictError("Recovery found a newer GNOME accent; backup retained.")
        current_state = _read(self.state_file)
        expected_state = json.dumps(journal["state_after"], indent=2).encode()
        if current_state not in (_decode(journal["state_before"]), expected_state):
            raise ConflictError("Recovery found newer Accented state; backup retained.")
        for name, value in journal["before"].items():
            _write(self.config / name, _decode(value))
        if journal["change_shell"]:
            self.settings.restore(journal["shell_before"])
        _write(self.state_file, _decode(journal["state_before"]))
        self.journal.unlink()
        return True

    def recover(self) -> bool:
        with self._lock():
            return self._recover()

    def apply(self, value: str, *, modern: bool = True, dark: bool = False,
              match_shell: bool = False) -> Path:
        value = normalize_hex(value)
        with self._lock():
            if self.journal.exists():
                raise ConflictError("An interrupted change needs recovery. Use Restore first.")
            previous = self.state()
            files = previous.get("files", {})
            changes, records = {}, {}
            for name in TARGETS:
                raw = _read(self.config / name)
                clean = self._unmanaged(raw, files.get(name))
                block = accent_css(value, modern=modern and name.startswith("gtk-4"), dark=dark)
                changes[name] = (clean or b"") + block.encode()
                records[name] = {"block": block, "original_missing": clean is None}
            before, after, baseline = None, None, previous.get("shell_baseline")
            change_shell = match_shell
            if match_shell:
                if self.settings is None or not self.settings.available:
                    raise ConflictError("GNOME's native accent preference is unavailable.")
                before = self.settings.snapshot()
                baseline = before if previous.get("shell_applied") is None else baseline
                if previous.get("shell_applied") is not None and before != previous["shell_applied"]:
                    # A deliberate new Apply adopts the current external setting as baseline.
                    baseline = before
                after = {"user_value": nearest_preset(value)}
            elif previous.get("shell_applied") is not None:
                if self.settings is None or not self.settings.available:
                    raise ConflictError("GNOME settings are unavailable; restore has been paused.")
                before = self.settings.snapshot()
                if before == previous["shell_applied"]:
                    after, change_shell = baseline, True
                baseline = None
            state = {"schema": 1, "color": value, "files": records,
                     "shell_baseline": baseline, "shell_applied": after if match_shell else None,
                     "recent": list(dict.fromkeys([value] + previous.get("recent", [])))[:10]}
            return self._transaction(changes, state, before, after, change_shell)

    def restore(self) -> tuple[bool, str]:
        with self._lock():
            if self.journal.exists():
                self._recover()
                return True, "Recovered the interrupted change. Review before applying again."
            previous = self.state()
            if not previous.get("files"):
                return False, "There are no Accented changes to restore."
            if set(previous["files"]) != set(TARGETS):
                raise ConflictError("Unexpected owned CSS paths; no configuration was changed.")
            changes = {name: self._unmanaged(_read(self.config / name), record)
                       for name, record in previous["files"].items()}
            before, after, change = None, None, False
            note = "Original app accents restored. Reopen apps to see the change."
            if previous.get("shell_applied") is not None:
                if self.settings is None or not self.settings.available:
                    raise ConflictError("GNOME settings are unavailable; restore has been paused.")
                before = self.settings.snapshot()
                if before == previous["shell_applied"]:
                    after, change = previous["shell_baseline"], True
                else:
                    note += " Your newer GNOME accent was left alone."
            state = {"schema": 1, "recent": previous.get("recent", [])}
            self._transaction(changes, state, before, after, change)
            return True, note
