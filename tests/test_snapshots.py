import json
from pathlib import Path
import tempfile
import unittest
from opsvault import backup, restore, verify


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'empty').mkdir()
        (self.source / 'notes.txt').write_text('restore me\n')
        (self.source / 'binary').write_bytes(bytes(range(256)))
        self.snapshot = self.root / 'snapshot'

    def test_roundtrip_preserves_content_and_empty_directories(self):
        self.assertEqual(backup(self.source, self.snapshot)['files'], 2)
        self.assertEqual(len(verify(self.snapshot)['files']), 2)
        target = self.root / 'recovered'
        restore(self.snapshot, target)
        self.assertEqual((target / 'binary').read_bytes(), bytes(range(256)))
        self.assertEqual((target / 'notes.txt').read_text(), 'restore me\n')
        self.assertTrue((target / 'empty').is_dir())

    def test_corruption_stops_restore(self):
        backup(self.source, self.snapshot)
        (self.snapshot / 'data/notes.txt').write_text('tampered')
        target = self.root / 'recovered'
        with self.assertRaises(ValueError):
            restore(self.snapshot, target)
        self.assertFalse(target.exists())

    def test_existing_destination_is_preserved(self):
        backup(self.source, self.snapshot)
        with self.assertRaises(ValueError):
            backup(self.source, self.snapshot)
        with self.assertRaises(ValueError):
            restore(self.snapshot, self.source)
        self.assertEqual((self.source / 'notes.txt').read_text(), 'restore me\n')

    def test_source_symlinks_and_nested_destinations_are_rejected(self):
        (self.source / 'link').symlink_to(self.source / 'notes.txt')
        with self.assertRaises(ValueError):
            backup(self.source, self.snapshot)
        with self.assertRaises(ValueError):
            backup(self.source, self.source / 'nested')

    def test_unsafe_manifest_is_rejected(self):
        backup(self.source, self.snapshot)
        path = self.snapshot / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files']['../escape'] = {'bytes': 0, 'sha256': 'fake'}
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            verify(self.snapshot)

    def test_added_file_is_detected(self):
        backup(self.source, self.snapshot)
        (self.snapshot / 'data/unexpected').write_text('extra')
        with self.assertRaises(ValueError):
            verify(self.snapshot)

if __name__ == '__main__':
    unittest.main()
