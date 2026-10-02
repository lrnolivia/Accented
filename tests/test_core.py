import base64
import json
import math
import os
from pathlib import Path
import random
import stat
import tempfile
import unittest
from unittest.mock import patch
from accented import core


class Settings:
    available = True
    def __init__(self, value=None):
        self.value = value
        self.fail_once = False
    def snapshot(self):
        return {"user_value": self.value}
    def restore(self, snapshot):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("simulated settings write failure")
        self.value = snapshot["user_value"]


class ColorTests(unittest.TestCase):
    def test_normalize(self):
        for before, after in [("db805a", "#DB805A"),(" #da8 ","#DDAA88"),("000000","#000000")]:
            self.assertEqual(core.normalize_hex(before),after)
    def test_invalid_input(self):
        for color in ("", "#12", "#1234", "#12345678", "red", "#xxccdd", "#123;{}"):
            with self.subTest(color=color), self.assertRaises(ValueError):
                core.normalize_hex(color)
    def test_rgb_roundtrip(self):
        for color in core.PRESETS.values():
            self.assertEqual(core.from_rgb(core.rgb(color)),color)
    def test_invalid_portal_values(self):
        for value in [(-.1,0,0),(0,0,1.1),(0,0,float('nan')),(0,float('inf'),0),(0,0),(0,0,0,0)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.from_rgb(value)
    def test_portal_rounding(self):
        self.assertEqual(core.from_rgb((.5, 0, 1)), '#8000FF')
    def test_foreground_contrast(self):
        rng = random.Random(42)
        for _ in range(1000):
            color=f'#{rng.randrange(1<<24):06X}'
            self.assertGreaterEqual(core.contrast(color,core.foreground(color)),4.5)
    def test_standalone_contrast(self):
        for color in list(core.PRESETS.values())+['#FFFFFF','#000000','#DB805A']:
            for dark in (True,False):
                self.assertGreaterEqual(core.contrast(core.standalone(color,dark), '#242424' if dark else '#FFFFFF'),4.5)
    def test_nearest_presets(self):
        for name, color in core.PRESETS.items():
            self.assertEqual(core.nearest_preset(color),name)
    def test_no_theme_replacement(self):
        css=core.accent_css('#DB805A',modern=True)
        for forbidden in ('font-', 'padding:', 'border-radius:', 'window_bg_color', 'url(', '@import', 'gradient'):
            self.assertNotIn(forbidden,css)
        self.assertIn('--accent-bg-color: #DB805A;',css)
    def test_legacy_css_has_no_custom_properties(self):
        self.assertNotIn('--',core.accent_css('#DB805A',modern=False))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.config=self.root/'config'
        self.settings=Settings()
        self.store=core.AccentStore(self.config,self.root/'state',self.settings)
    def tearDown(self):
        self.temp.cleanup()
    def write_css(self,name,raw):
        p=self.config/name; p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    def css(self,name):
        p=self.config/name
        return p.read_bytes() if p.exists() else None
    def test_read_only_before_apply(self):
        self.assertEqual(self.store.state(),{})
        self.assertFalse(self.config.exists())
        self.assertFalse(self.store.root.exists())
    def test_apply_restore_missing(self):
        backup=self.store.apply('#DB805A')
        self.assertTrue((backup/'transaction.json').is_file())
        for name in core.TARGETS:
            self.assertIn(b'#DB805A',self.css(name))
        self.assertTrue(self.store.restore()[0])
        for name in core.TARGETS:self.assertIsNone(self.css(name))
    def test_existing_css_preserved_exactly(self):
        for name in core.TARGETS:self.write_css(name,b'/* existing */\r\n@import "my-theme.css";\n')
        self.store.apply('#da8')
        self.store.restore()
        for name in core.TARGETS:self.assertEqual(self.css(name),b'/* existing */\r\n@import "my-theme.css";\n')
    def test_empty_existing_file_remains(self):
        for name in core.TARGETS:self.write_css(name,b'')
        self.store.apply('#DB805A');self.store.restore()
        for name in core.TARGETS:self.assertEqual(self.css(name),b'')
    def test_external_append_retained(self):
        self.store.apply('#DB805A')
        for name in core.TARGETS:self.write_css(name,self.css(name)+b'/* later edit */\n')
        self.store.restore()
        for name in core.TARGETS:self.assertEqual(self.css(name),b'/* later edit */\n')
    def test_reapply_one_block(self):
        self.store.apply('#DB805A');self.store.apply('#123456')
        for name in core.TARGETS:
            self.assertEqual(self.css(name).count(core.BEGIN.encode()),1)
            self.assertNotIn(b'#DB805A',self.css(name))
        self.store.restore()
        self.assertIsNone(self.css(core.TARGETS[0]))
    def test_recent_deduplication_and_cap(self):
        for i in range(12):self.store.apply(f'#{i:06X}')
        self.store.apply('#000005')
        self.assertEqual(self.store.state()['recent'][0],'#000005')
        self.assertEqual(len(self.store.state()['recent']),10)
    def test_unknown_owned_block_refused(self):
        self.write_css(core.TARGETS[1],core.accent_css('#000',modern=True).encode())
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
        self.assertIsNone(self.css(core.TARGETS[0]))
    def test_modified_owned_block_refused(self):
        self.store.apply('#DB805A')
        name=core.TARGETS[1]; changed=self.css(name).replace(b'#DB805A',b'#112233')
        self.write_css(name,changed)
        for op in (self.store.restore,lambda:self.store.apply('#ffeedd')):
            with self.assertRaises(core.ConflictError):op()
        self.assertEqual(self.css(name),changed)
    def test_symlink_file_refused(self):
        p=self.config/core.TARGETS[0];p.parent.mkdir(parents=True)
        target=self.root/'other';target.write_text('unrelated')
        p.symlink_to(target)
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
        self.assertEqual(target.read_text(),'unrelated')
    def test_symlink_parent_refused(self):
        self.config.mkdir(); target=self.root/'other';target.mkdir()
        (self.config/'gtk-4.0').symlink_to(target,target_is_directory=True)
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
        self.assertEqual(list(target.iterdir()),[])
        self.assertIsNone(self.css(core.TARGETS[0]))
    def test_system_owned_ancestor_symlink_allowed(self):
        real_root=self.root/'var-home';real_root.mkdir()
        system_home=self.root/'home';system_home.symlink_to(real_root,target_is_directory=True)
        home=system_home/'loew'
        store=core.AccentStore(home/'.config',home/'.local/state',self.settings)
        # Model Bazzite's root-owned /home symlink by making its actual owner
        # differ from the effective uid seen by Accented.
        with patch.object(core.os,'geteuid',return_value=os.geteuid()+1):
            store.apply('#DB805A')
            changed=(home/'.config'/core.TARGETS[0]).read_bytes()
            self.assertIn(b'#DB805A',changed)
            self.assertTrue(store.restore()[0])
    def test_directory_target_refused(self):
        (self.config/core.TARGETS[1]).mkdir(parents=True)
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
    def test_non_utf8_refused(self):
        self.write_css(core.TARGETS[1],b'\xff\xfe')
        with self.assertRaises(UnicodeError):self.store.apply('#DB805A')
        self.assertIsNone(self.css(core.TARGETS[0]))
    def test_file_mode_retained(self):
        for name in core.TARGETS:
            self.write_css(name,b'original')
            (self.config/name).chmod(0o640)
        self.store.apply('#DB805A')
        self.assertEqual(stat.S_IMODE((self.config/core.TARGETS[0]).stat().st_mode),0o640)
    def test_shell_off_unchanged(self):
        self.settings.value='teal'
        self.store.apply('#DB805A')
        self.assertEqual(self.settings.value,'teal')
    def test_shell_match_and_restore(self):
        self.settings.value='teal'
        self.store.apply('#DB805A',match_shell=True)
        self.assertEqual(self.settings.value,core.nearest_preset('#DB805A'))
        self.store.restore();self.assertEqual(self.settings.value,'teal')
    def test_shell_default_restored_as_unset(self):
        self.store.apply('#DB805A',match_shell=True)
        self.store.restore();self.assertIsNone(self.settings.value)
    def test_newer_external_shell_preserved(self):
        self.store.apply('#DB805A',match_shell=True)
        self.settings.value='purple'
        self.store.restore();self.assertEqual(self.settings.value,'purple')
    def test_unchecking_shell_restores_owned_match(self):
        self.settings.value='teal'
        self.store.apply('#DB805A',match_shell=True)
        self.store.apply('#aabbcc',match_shell=False)
        self.assertEqual(self.settings.value,'teal')
        self.assertIsNone(self.store.state()['shell_applied'])
        self.assertIn(b'#AABBCC',self.css(core.TARGETS[0]))
    def test_unchecking_shell_preserves_newer_external(self):
        self.store.apply('#DB805A',match_shell=True)
        self.settings.value='purple'
        self.store.apply('#aabbcc',match_shell=False)
        self.assertEqual(self.settings.value,'purple')
    def test_unavailable_shell_no_partial_writes(self):
        self.settings.available=False
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A',match_shell=True)
        self.assertIsNone(self.css(core.TARGETS[0]))
    def test_shell_failure_rolls_back_both_css_files(self):
        self.settings.fail_once=True
        with self.assertRaisesRegex(RuntimeError,'simulated'):self.store.apply('#DB805A',match_shell=True)
        for name in core.TARGETS:self.assertIsNone(self.css(name))
        self.assertFalse(self.store.journal.exists())
    def test_file_failure_rolls_back(self):
        real=core._write
        hit=False
        def fail(path,raw):
            nonlocal hit
            if path==self.config/core.TARGETS[1] and not hit:
                hit=True;raise OSError('disk write failure')
            real(path,raw)
        with patch.object(core,'_write',side_effect=fail),self.assertRaises(OSError):
            self.store.apply('#DB805A')
        for name in core.TARGETS:self.assertIsNone(self.css(name))
        self.assertFalse(self.store.journal.exists())
    def test_interrupted_write_recovery(self):
        real=core._write
        def power_loss(path,raw):
            if path==self.config/core.TARGETS[1]:raise KeyboardInterrupt()
            real(path,raw)
        with patch.object(core,'_write',side_effect=power_loss),self.assertRaises(KeyboardInterrupt):
            self.store.apply('#DB805A')
        self.assertTrue(self.store.journal.exists())
        self.assertTrue(self.store.recover())
        for name in core.TARGETS:self.assertIsNone(self.css(name))
    def test_recovery_preserves_external_edit(self):
        real=core._write
        def power_loss(path,raw):
            if path==self.config/core.TARGETS[1]:raise KeyboardInterrupt()
            real(path,raw)
        with patch.object(core,'_write',side_effect=power_loss),self.assertRaises(KeyboardInterrupt):
            self.store.apply('#DB805A')
        self.write_css(core.TARGETS[0],b'newer edit')
        with self.assertRaises(core.ConflictError):self.store.recover()
        self.assertEqual(self.css(core.TARGETS[0]),b'newer edit')
    def test_pending_change_blocks_apply(self):
        self.store.root.mkdir(parents=True)
        self.store.journal.write_text('{}')
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
    def test_unknown_state_version_refused(self):
        self.store.root.mkdir(parents=True)
        self.store.state_file.write_text('{"schema":99}')
        with self.assertRaises(core.ConflictError):self.store.apply('#DB805A')
    def test_concurrent_writer_refused(self):
        with self.store._lock(),self.assertRaises(core.ConflictError):
            core.AccentStore(self.config,self.root/'state',self.settings).apply('#DB805A')
    def test_restore_twice_is_noop(self):
        self.store.apply('#DB805A');self.store.restore()
        self.assertFalse(self.store.restore()[0])


if __name__ == '__main__': unittest.main()
