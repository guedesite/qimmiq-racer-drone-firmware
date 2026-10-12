"""Read-only extraction of saved UAVObjects from an external OpenPilot LogFS dump."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from uavo_schema import decode_payload

ARENA_ACTIVE = 0xe6e66666
SLOT_ACTIVE = 0xfafaaaaa
SLOT_EMPTY = 0xffffffff


def extract(data, schema, magic=0x99abceef, arena_size=0x10000, slot_size=0x100):
    if len(data) % arena_size:
        raise ValueError('Incomplete arena in flash dump')
    if arena_size % slot_size or slot_size < 12:
        raise ValueError('Invalid LogFS geometry')
    arenas = []
    for off in range(0, len(data), arena_size):
        signature, state = struct.unpack_from('<II', data, off)
        arenas.append({'index': off//arena_size, 'offset': off,
                       'magic': hex(signature), 'state': hex(state),
                       'active': signature == magic and state == ARENA_ACTIVE})
    active = [a for a in arenas if a['active']]
    if not active:
        raise ValueError('No active LogFS arena with expected magic')
    # Exact upstream mount behavior: select the lowest-numbered active arena.
    chosen = active[0]
    by_id = {int(o['id'], 16): o for o in schema['objects']}
    records, seen, warnings = [], set(), []
    if len(active) > 1:
        warnings.append('Multiple active arenas: possible interrupted collection; upstream selects the first.')
    for slot in range(1, arena_size//slot_size):
        off = chosen['offset'] + slot*slot_size
        state, obj_id, instance, size = struct.unpack_from('<IIHH', data, off)
        if state == SLOT_EMPTY:
            break  # Upstream object lookup also stops here.
        if state != SLOT_ACTIVE:
            continue
        if size > slot_size-12:
            warnings.append('Invalid object size in slot ' + str(slot))
            continue
        key = (obj_id, instance)
        if key in seen:
            warnings.append('Duplicate active object: first entry retained, slot ' + str(slot))
            continue
        seen.add(key)
        payload = data[off+12:off+12+size]
        record = {'slot': slot, 'offset': off, 'id': '0x%08x' % obj_id,
                  'instance': instance, 'size': size, 'payload_hex': payload.hex()}
        obj = by_id.get(obj_id)
        if obj:
            record.update(name=obj['name'], settings=obj['settings'])
            if size == obj['size']:
                record['fields'] = decode_payload(obj, payload)
                record['equals_factory_payload'] = payload.hex() == obj['factory_payload_hex']
            else:
                record['schema_error'] = 'Stored size differs from expected ' + str(obj['size'])
        else:
            record['schema_error'] = 'Unknown object ID; preserve raw bytes'
        records.append(record)
    return {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
            'uavo_sha1': schema['uavo_sha1'], 'arenas': arenas,
            'selected_arena': chosen['index'], 'objects': records, 'warnings': warnings,
            'limits': 'LogFS has no payload CRC in this format. Verify repeat reads. '
                      'Missing objects do not prove factory defaults are currently in use.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('external_dump', type=Path)
    p.add_argument('--schema', type=Path, default=Path('analysis/baseline/uavo_schema.json'))
    p.add_argument('--expected-size', type=lambda s: int(s, 0), default=0x200000)
    p.add_argument('--magic', type=lambda s: int(s, 0), default=0x99abceef)
    p.add_argument('--out', type=Path, default=Path('analysis/saved_settings.json'))
    args = p.parse_args()
    data = args.external_dump.read_bytes()
    if len(data) != args.expected_size:
        raise ValueError('Expected external flash size ' + hex(args.expected_size) + '; got ' + hex(len(data)))
    report = extract(data, json.loads(args.schema.read_text(encoding='utf-8')), magic=args.magic)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(len(report['objects']), 'saved objects; active arena:', report['selected_arena'])


if __name__ == '__main__':
    main()
