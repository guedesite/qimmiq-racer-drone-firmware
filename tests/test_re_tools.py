"""Check evidence extraction and patch refusal cases without altering firmware.bin."""
import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_dump import inspect, vector_candidates
from patch_image import apply_manifest
from match_functions import rank


class ToolsTest(unittest.TestCase):
    def test_word_aligned_initial_stack_is_accepted(self):
        data = bytearray(512)
        words = [0x2000023c] + [0x08000101]*58
        struct.pack_into('<59I', data, 0, *words)
        result = vector_candidates(data)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]['sp_aligned_8'])
        struct.pack_into('<I', data, 4, 0x08000100)
        self.assertEqual(vector_candidates(data), [])

    def test_actual_dump_evidence(self):
        data = (Path(__file__).resolve().parents[1] / 'firmware.bin').read_bytes()
        report = inspect(data)
        self.assertEqual(report['sha256'], 'ec90df9a62bfb389fe555c82dd5192eda0db17ec880896aa340456b8e15de3fc')
        self.assertEqual([t['offset'] for t in report['vector_candidates']], [0, 0x3000])
        self.assertEqual(len(report['openpilot_descriptors']), 2)
        for descriptor in report['openpilot_descriptors']:
            self.assertEqual(descriptor['commit_prefix'], 'bf68cc84')
            self.assertEqual(descriptor['board_type'], 4)
            self.assertEqual(descriptor['board_revision'], 2)
            self.assertEqual(descriptor['verified_hash_ranges'],
                             [{'start': '0x8003000', 'end_exclusive': '0x801a698'}])

    def test_patch_guards(self):
        source = bytes(range(16))
        manifest = {'source_sha256': hashlib.sha256(source).hexdigest(), 'size': 16,
                    'base': '0x08000000', 'patches': [
                        {'address': '0x08000002', 'before': '0203', 'after': '00bf', 'kind': 'thumb_code'}]}
        self.assertEqual(apply_manifest(source, manifest)[2:4], b'\x00\xbf')
        manifest['patches'].append(dict(manifest['patches'][0]))
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            apply_manifest(source, manifest)
        manifest['patches'].pop()
        manifest['patches'][0]['before'] = 'ffff'
        with self.assertRaisesRegex(ValueError, 'original bytes'):
            apply_manifest(source, manifest)
        manifest['source_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            apply_manifest(source, manifest)

    def test_match_keeps_collisions_as_candidates(self):
        f = {'address': '08001000', 'name': 'unknown', 'instruction_count': 20,
             'normalized_blocks': ['b'], 'shingles_5': ['s1','s2']}
        result = rank([f], [dict(f, name='one'), dict(f, name='two')])
        self.assertEqual(len(result[0]['candidates']), 2)
        self.assertEqual(result[0]['status'], 'manual_validation_required')


if __name__ == '__main__':
    unittest.main()
