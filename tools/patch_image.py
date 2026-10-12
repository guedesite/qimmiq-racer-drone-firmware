"""Apply a reviewed byte manifest to a NEW file, without flashing or guessing checksums."""
import argparse
import hashlib
import json
from pathlib import Path


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def apply_manifest(source, manifest):
    if hashlib.sha256(source).hexdigest() != manifest['source_sha256']:
        raise ValueError('Source SHA256 mismatch')
    if len(source) != number(manifest['size']):
        raise ValueError('Source size mismatch')
    base = number(manifest['base'])
    output = bytearray(source)
    occupied = set()
    for patch in manifest['patches']:
        off = number(patch['address']) - base
        before, after = bytes.fromhex(patch['before']), bytes.fromhex(patch['after'])
        if not before or len(before) != len(after):
            raise ValueError('Each patch must be nonempty and preserve size')
        if off < 0 or off+len(before) > len(source):
            raise ValueError('Patch outside image')
        if patch.get('kind') == 'thumb_code' and (off % 2 or len(after) % 2):
            raise ValueError('Thumb code must preserve halfword alignment')
        span = set(range(off, off+len(before)))
        if occupied & span:
            raise ValueError('Overlapping patches')
        occupied |= span
        if source[off:off+len(before)] != before:
            raise ValueError('Expected original bytes do not match at ' + hex(base+off))
        output[off:off+len(after)] = after
    return bytes(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('manifest', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError('Output must differ from the original dump')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    output = apply_manifest(args.source.read_bytes(), manifest)
    # Exclusive creation prevents silently overwriting another artifact.
    with args.output.open('xb') as stream:
        stream.write(output)
    print('New SHA256:', hashlib.sha256(output).hexdigest())
    print('Integrity metadata must be recomputed separately using the verified upstream format.')


if __name__ == '__main__':
    main()
