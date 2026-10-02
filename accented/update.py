"""Small, verified self-updater for the installed Accented app."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlparse

UPDATE_MANIFEST_URL = os.environ.get(
    "ACCENTED_UPDATE_MANIFEST",
    "https://raw.githubusercontent.com/lrnolivia/Accented-Updates/main/stable.json",
)
ALLOWED_HOST = "raw.githubusercontent.com"
ALLOWED_PATH_PREFIX = "/lrnolivia/Accented-Updates/"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_INSTALLER_BYTES = 2 * 1024 * 1024


class UpdateError(RuntimeError):
    """The update feed, download, or installer could not be trusted/completed."""


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    notes: str = ""


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        raise UpdateError("The update service returned an invalid version.")
    return tuple(int(p) for p in parts)


def is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def _safe_user_path(path: Path) -> None:
    path = path.absolute()
    uid = os.geteuid()
    for candidate in (path, *path.parents):
        if not candidate.is_symlink():
            continue
        if candidate == path or os.lstat(candidate).st_uid == uid:
            raise UpdateError(f"Refusing a symbolic link: {candidate}")


def _atomic_json(path: Path, value: dict) -> None:
    _safe_user_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".accented-pref-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Preferences:
    def __init__(self, config_root: Path):
        self.path = config_root.absolute() / "accented" / "preferences.json"

    def load(self) -> dict:
        _safe_user_path(self.path)
        if not self.path.exists():
            return {"schema": 1, "auto_update": True}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UpdateError(f"Could not read update preferences: {exc}") from exc
        if value.get("schema") != 1 or not isinstance(value.get("auto_update"), bool):
            raise UpdateError("Unrecognized Accented update preferences.")
        return value

    def auto_update(self) -> bool:
        return self.load()["auto_update"]

    def set_auto_update(self, enabled: bool) -> None:
        _atomic_json(self.path, {"schema": 1, "auto_update": bool(enabled)})


class UpdateClient:
    def __init__(self, current_version: str, manifest_url: str = UPDATE_MANIFEST_URL,
                 opener=None, runner=None):
        self.current_version = current_version
        self.manifest_url = manifest_url
        self.opener = opener or urllib.request.urlopen
        self.runner = runner or subprocess.run

    def _fetch(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"Accented/{self.current_version}"},
        )
        try:
            with self.opener(request, timeout=12) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise UpdateError(f"Update service returned HTTP {status}.")
                raw = response.read(limit + 1)
        except UpdateError:
            raise
        except (OSError, urllib.error.URLError) as exc:
            raise UpdateError(f"Could not reach the update service: {exc}") from exc
        if len(raw) > limit:
            raise UpdateError("The update service returned an unexpectedly large file.")
        return raw

    @staticmethod
    def _validate_download_url(url: str) -> None:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or
                not parsed.path.startswith(ALLOWED_PATH_PREFIX)):
            raise UpdateError("The update service returned an untrusted download address.")

    def check(self) -> Release | None:
        try:
            payload = json.loads(self._fetch(self.manifest_url, MAX_MANIFEST_BYTES))
        except json.JSONDecodeError as exc:
            raise UpdateError("The update service returned invalid metadata.") from exc
        if payload.get("schema") != 1:
            raise UpdateError("The update service returned an unsupported manifest.")
        version = payload.get("version")
        url = payload.get("url")
        checksum = payload.get("sha256")
        notes = payload.get("notes", "")
        if not all(isinstance(v, str) for v in (version, url, checksum, notes)):
            raise UpdateError("The update service returned incomplete metadata.")
        version_tuple(version)
        if len(checksum) != 64 or any(c not in "0123456789abcdefABCDEF" for c in checksum):
            raise UpdateError("The update service returned an invalid checksum.")
        self._validate_download_url(url)
        if not is_newer(version, self.current_version):
            return None
        return Release(version=version, url=url, sha256=checksum.lower(), notes=notes.strip())

    def install(self, release: Release) -> str:
        self._validate_download_url(release.url)
        raw = self._fetch(release.url, MAX_INSTALLER_BYTES)
        actual = hashlib.sha256(raw).hexdigest()
        if actual != release.sha256:
            raise UpdateError("Downloaded update checksum did not match. Nothing was installed.")
        fd, name = tempfile.mkstemp(prefix="Accented-update-", suffix=".run")
        path = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            result = self.runner(
                ["/bin/bash", str(path)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout or "Installer failed.").strip()
                raise UpdateError(detail)
            return (result.stdout or f"Updated to {release.version}.").strip()
        except subprocess.TimeoutExpired as exc:
            raise UpdateError("The update installer timed out. Nothing else was attempted.") from exc
        finally:
            path.unlink(missing_ok=True)
