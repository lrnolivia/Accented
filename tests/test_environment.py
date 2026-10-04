import os,json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from accented.environment import storage_paths,is_flatpak
ROOT=Path(__file__).resolve().parents[1]
class SandboxPathsTests(unittest.TestCase):
    def test_native_paths_unchanged(self):
        with patch.dict(os.environ,{},clear=True):self.assertEqual(storage_paths('/tmp/config','/tmp/state'),(Path('/tmp/config'),Path('/tmp/state')))
    def test_flatpak_uses_explicit_host_grants_and_shared_recovery_state(self):
        with patch.dict(os.environ,{'FLATPAK_ID':'com.loew.accented','HOST_XDG_CONFIG_HOME':'/host/custom-config','HOST_XDG_STATE_HOME':'/host/custom-state','XDG_CONFIG_HOME':'/app-private/config','XDG_STATE_HOME':'/app-private/state'},clear=True):
            self.assertTrue(is_flatpak());self.assertEqual(storage_paths(),(Path('/host/custom-config'),Path('/host/custom-state')))
    def test_relative_host_paths_fail_closed(self):
        with patch.dict(os.environ,{'FLATPAK_ID':'com.loew.accented','HOST_XDG_CONFIG_HOME':'relative'},clear=True):
            with self.assertRaises(ValueError):storage_paths()
    def test_flatpak_grants_are_narrow_and_have_no_host_execution_or_network(self):
        manifest=json.loads((ROOT/'packaging/flatpak/com.loew.accented.json').read_text());args=manifest['finish-args']
        self.assertEqual({x for x in args if x.startswith('--filesystem=')},{'--filesystem=xdg-config/gtk-3.0:create','--filesystem=xdg-config/gtk-4.0:create','--filesystem=~/.local/state/accented:create'})
        self.assertFalse(any('talk-name' in x or x=='--share=network' or x=='--filesystem=home' for x in args));self.assertEqual(manifest['runtime-version'],'50')
