from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import Mock

from accented.update import (
    Preferences,
    Release,
    UpdateClient,
    UpdateError,
    is_newer,
)


class Response:
    def __init__(self, raw, status=200):
        self.raw = raw
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, _size=-1):
        return self.raw


class UpdateTests(unittest.TestCase):
    def manifest(self, version="0.3.0", raw=b"installer"):
        return json.dumps({
            "schema": 1,
            "version": version,
            "url": "https://raw.githubusercontent.com/lrnolivia/Accented-Updates/main/Accented.run",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "notes": "Small update.",
        }).encode()

    def test_version_compare(self):
        self.assertTrue(is_newer("0.2.1", "0.2.0"))
        self.assertFalse(is_newer("0.2.0", "0.2.0"))
        self.assertFalse(is_newer("0.1.9", "0.2.0"))
        with self.assertRaises(UpdateError):
            is_newer("latest", "0.2.0")

    def test_check_returns_new_release(self):
        client = UpdateClient("0.2.0", opener=lambda *_a, **_k: Response(self.manifest()))
        release = client.check()
        self.assertEqual(release.version, "0.3.0")
        self.assertIn("Small update", release.notes)

    def test_check_current_version_is_noop(self):
        client = UpdateClient("0.2.0", opener=lambda *_a, **_k: Response(self.manifest("0.2.0")))
        self.assertIsNone(client.check())

    def test_untrusted_download_url_refused(self):
        payload = json.loads(self.manifest())
        payload["url"] = "https://example.com/Accented.run"
        client = UpdateClient("0.2.0", opener=lambda *_a, **_k: Response(json.dumps(payload).encode()))
        with self.assertRaisesRegex(UpdateError, "untrusted"):
            client.check()

    def test_bad_checksum_refused_before_installer(self):
        manifest = self.manifest(raw=b"expected")
        calls = []
        def opener(request, **_kwargs):
            calls.append(request.full_url)
            return Response(manifest if len(calls) == 1 else b"different")
        runner = Mock()
        client = UpdateClient("0.2.0", opener=opener, runner=runner)
        release = client.check()
        with self.assertRaisesRegex(UpdateError, "checksum"):
            client.install(release)
        runner.assert_not_called()

    def test_verified_update_runs_guarded_installer(self):
        installer = b"#!/bin/bash\necho ok\n"
        manifest = self.manifest(raw=installer)
        calls = []
        def opener(request, **_kwargs):
            calls.append(request.full_url)
            return Response(manifest if len(calls) == 1 else installer)
        result = Mock(returncode=0, stdout="installed\n", stderr="")
        runner = Mock(return_value=result)
        client = UpdateClient("0.2.0", opener=opener, runner=runner)
        release = client.check()
        self.assertEqual(client.install(release), "installed")
        args = runner.call_args.args[0]
        self.assertEqual(args[0], "/bin/bash")
        self.assertFalse(Path(args[1]).exists(), "temporary installer should be deleted")

    def test_preferences_default_on_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            prefs = Preferences(Path(folder))
            self.assertTrue(prefs.auto_update())
            prefs.set_auto_update(False)
            self.assertFalse(prefs.auto_update())


if __name__ == "__main__":
    unittest.main()
