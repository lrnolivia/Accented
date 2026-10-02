from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import install as setup

SOURCE=Path(__file__).resolve().parent.parent

class FakeStore:
    def __init__(self):self.calls=0
    def restore(self):self.calls+=1;return True,'Restored.'

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='accented test ')
        self.home=Path(self.tmp.name)/'home with spaces'
        self.data=self.home/'.local/share'
        self.dest,self.outside=setup.locations(self.home,self.data)
        self.refresh=patch.object(setup,'refresh');self.refresh.start()
    def tearDown(self):self.refresh.stop();self.tmp.cleanup()
    def go(self):return setup.install(SOURCE,self.home,self.data)
    def test_install_and_metadata(self):
        launcher=self.go()
        self.assertTrue(launcher.stat().st_mode&0o100)
        self.assertIn('home with spaces',launcher.read_text())
        self.assertIn('Name=Accented',self.outside['desktop'].read_text())
        self.assertEqual(set(setup.marker(self.dest)['files']),set(setup.PACKAGE_FILES))
        self.assertFalse((self.home/'.config/gtk-4.0/gtk.css').exists())
    def test_repeat_install(self):
        self.go();self.go()
        self.assertTrue((self.dest/'launch.py').is_file())
        self.assertFalse(list(self.data.glob('.accented-old-*')))
    def test_conflicting_launcher(self):
        p=self.outside['launcher'];p.parent.mkdir(parents=True);p.write_text('unrelated')
        with self.assertRaisesRegex(RuntimeError,'Another file'):self.go()
        self.assertEqual(p.read_text(),'unrelated')
        self.assertFalse(self.dest.exists())
    def test_unknown_install_directory(self):
        self.dest.mkdir(parents=True)
        (self.dest/'my.txt').write_text('important')
        with self.assertRaisesRegex(RuntimeError,'not an Accented-owned'):self.go()
        self.assertEqual((self.dest/'my.txt').read_text(),'important')
    def test_modified_app_refused(self):
        self.go();(self.dest/'launch.py').write_text('edited')
        with self.assertRaisesRegex(RuntimeError,'edited or removed'):self.go()
        self.assertEqual((self.dest/'launch.py').read_text(),'edited')
    def test_extra_file_refused(self):
        self.go();(self.dest/'my.txt').write_text('new file')
        with self.assertRaisesRegex(RuntimeError,'Unexpected file'):self.go()
    def test_symlink_launcher_refused(self):
        target=self.home/'important';target.parent.mkdir(parents=True);target.write_text('safe')
        p=self.outside['launcher'];p.parent.mkdir(parents=True);p.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError,'symbolic link'):self.go()
        self.assertEqual(target.read_text(),'safe')
    def test_missing_source_refused(self):
        with self.assertRaisesRegex(RuntimeError,'Incomplete package'):
            setup.install(self.home/'missing',self.home,self.data)
        self.assertFalse(self.dest.exists())
    def test_uninstall_calls_restore_and_keeps_backups(self):
        self.go();store=FakeStore()
        backup=self.home/'.local/state/accented/backups/test';backup.mkdir(parents=True)
        (backup/'transaction.json').write_text('backup')
        self.assertEqual(setup.uninstall(store,self.home,self.data),0)
        self.assertEqual(store.calls,1)
        self.assertFalse(self.dest.exists())
        self.assertTrue((backup/'transaction.json').exists())
    def test_restore_failure_aborts_uninstall(self):
        self.go();store=FakeStore()
        with patch.object(store,'restore',side_effect=RuntimeError('conflict')):
            self.assertEqual(setup.uninstall(store,self.home,self.data),1)
        self.assertTrue((self.dest/'launch.py').exists())
    def test_update_rollback_on_external_write_failure(self):
        self.go();before=(self.dest/'launch.py').read_bytes()
        real=setup.write;failed=False
        def write(path,raw,mode=0o644):
            nonlocal failed
            if path==self.outside['desktop'] and not failed:
                failed=True;raise OSError('disk full')
            real(path,raw,mode)
        with patch.object(setup,'write',side_effect=write),self.assertRaises(OSError):self.go()
        self.assertEqual((self.dest/'launch.py').read_bytes(),before)
        setup.verify_owned(self.dest,self.outside,setup.marker(self.dest))
    def test_corrupt_install_record_refused(self):
        self.go();(self.dest/setup.MARKER).write_text('{"schema":99}')
        with self.assertRaisesRegex(RuntimeError,'Unrecognized'):self.go()

if __name__=='__main__':unittest.main()
