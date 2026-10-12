import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from uavo_schema import load_schema, decode_payload
from extract_logfs import extract, ARENA_ACTIVE, SLOT_ACTIVE
from compare_baseline import compare
from reconstruct_baseline import reconstruct

SOURCE = ROOT / 'analysis/baseline/LibrePilot-bf68cc84d471feb0d9346f40f012e6c8e4de4bbb'


class SettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A fresh clone can test the decoder without downloading the source tree.
        cls.schema = json.loads((ROOT / 'analysis/baseline/uavo_schema.json').read_text(encoding='utf-8'))

    def test_schema_matches_historical_hash_and_generated_ids(self):
        if SOURCE.exists():
            self.assertEqual(load_schema(SOURCE / 'shared/uavobjectdefinition'), self.schema)
        self.assertEqual(self.schema['uavo_sha1'], 'e700bb5174d04ca794312e6234a78b01469143df')
        self.assertEqual(len(self.schema['objects']), 104)
        self.assertEqual(sum(o['size'] for o in self.schema['objects']), 4228)
        self.assertEqual(sum(o['settings'] for o in self.schema['objects']), 35)
        generated = SOURCE / 'build/uavobject-synthetics/flight'
        if not generated.exists():
            return
        for obj in self.schema['objects']:
            text = (generated / (obj['name'].lower() + '.h')).read_text()
            obj_id = re.search(r'#define\s+\w+_OBJID\s+(0x[0-9a-fA-F]+)', text).group(1)
            self.assertEqual(int(obj_id, 16), int(obj['id'], 16), obj['name'])

    def test_external_logfs_uses_first_active_arena_and_ignores_obsolete(self):
        obj = next(o for o in self.schema['objects'] if o['name'] == 'FlightModeSettings')
        data = bytearray(b'\xff' * 0x20000)
        for offset in (0, 0x10000):
            struct.pack_into('<II', data, offset, 0x99abceef, ARENA_ACTIVE)
        payload = bytes.fromhex(obj['factory_payload_hex'])
        struct.pack_into('<IIHH', data, 0x100, 0, int(obj['id'], 16), 0, len(payload))
        struct.pack_into('<IIHH', data, 0x200, SLOT_ACTIVE, int(obj['id'], 16), 0, len(payload))
        data[0x20c:0x20c+len(payload)] = payload
        result = extract(data, self.schema)
        self.assertEqual(result['selected_arena'], 0)
        self.assertEqual(len(result['objects']), 1)
        record = result['objects'][0]
        self.assertEqual(record['slot'], 2)
        self.assertTrue(record['equals_factory_payload'])
        self.assertEqual(record['fields']['Stabilization3Settings']['Roll'], 'Rate')
        self.assertTrue(result['warnings'])

    def test_missing_or_invalid_logfs_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No active'):
            extract(b'\xff' * 0x10000, self.schema)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            extract(b'\xff' * 513, self.schema)

    def test_comparison_detects_one_byte_and_size_changes(self):
        original = (ROOT / 'firmware.bin').read_bytes()
        app = original[0x3000:0x1a698]
        self.assertTrue(compare(original, app)['identical'])
        changed = bytearray(app)
        changed[16] ^= 1
        self.assertEqual(compare(original, changed)['different_bytes'], 1)
        self.assertEqual(compare(original, app + b'\x00')['different_bytes'], 1)

    def test_reconstruction_preserves_original_boot_and_rejects_changed_app(self):
        original = (ROOT / 'firmware.bin').read_bytes()
        app, descriptor = original[0x3000:0x1a698], original[-100:]
        self.assertEqual(reconstruct(original, app, descriptor), original)
        changed = bytearray(app)
        changed[16] ^= 1
        with self.assertRaisesRegex(ValueError, 'does not match'):
            reconstruct(original, changed, descriptor)


if __name__ == '__main__':
    unittest.main()
