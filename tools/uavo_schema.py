"""Export OpenPilot XML field layouts, IDs and factory defaults (not saved settings)."""
import argparse
import copy
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

TYPES = ['int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32', 'float', 'enum']
FORMATS = dict(zip(TYPES, ['b', 'h', 'i', 'B', 'H', 'I', 'f', 'B']))
WIDTHS = {name: struct.calcsize('<' + fmt) for name, fmt in FORMATS.items()}


def update_hash(value, result):
    if isinstance(value, str):
        for byte in value.encode('latin1'):
            # Upstream QByteArray uses char; Qt/Linux char is signed.
            result = update_hash(byte if byte < 128 else byte-256, result)
        return result
    return (result ^ ((result << 5) + (result >> 2) + value)) & 0xffffffff


def names(element, attribute, child):
    if attribute in element.attrib:
        return [s.strip() for s in element.attrib[attribute].split(',') if s]
    return [n.text for n in element.findall(attribute + '/' + child) if n.text]


def parse_object(element):
    fields = []
    for node in element.findall('field'):
        if 'cloneof' in node.attrib:
            field = copy.deepcopy(next(f for f in fields if f['name'] == node.attrib['cloneof']))
            field['name'] = node.attrib['name']
        else:
            elems = names(node, 'elementnames', 'elementname')
            if not elems:
                elems = [str(i) for i in range(int(node.attrib['elements']))]
            defaults = [s.strip() for s in node.attrib.get('defaultvalue', '').split(',') if s]
            if len(defaults) == 1:
                defaults *= len(elems)
            if defaults and len(defaults) != len(elems):
                raise ValueError('Invalid defaults: ' + node.attrib['name'])
            field = {'name': node.attrib['name'], 'type': node.attrib['type'], 'elements': elems,
                     'options': names(node, 'options', 'option'), 'defaults': defaults,
                     'units': node.attrib.get('units', '')}
        fields.append(field)
    fields.sort(key=lambda f: -WIDTHS[f['type']])  # Stable, like qStableSort.
    result = {'name': element.attrib['name'], 'settings': element.attrib['settings'] == 'true',
              'singleinstance': element.attrib['singleinstance'] == 'true', 'fields': fields}
    obj_hash = update_hash(result['name'], 0)
    obj_hash = update_hash(int(result['settings']), obj_hash)
    obj_hash = update_hash(int(result['singleinstance']), obj_hash)
    offset, default_blob = 0, bytearray()
    for field in fields:
        field['offset'] = offset
        count, kind = len(field['elements']), field['type']
        obj_hash = update_hash(field['name'], obj_hash)
        obj_hash = update_hash(count, obj_hash)
        obj_hash = update_hash(TYPES.index(kind), obj_hash)
        if kind == 'enum':
            for option in field['options']:
                obj_hash = update_hash(option, obj_hash)
        vals = []
        for text in field['defaults']:
            if kind == 'enum':
                # Match QStringList.indexOf and assignment to uint8_t in the
                # historical generator, including malformed default values.
                value = field['options'].index(text) if text in field['options'] else 255
                if value == 255:
                    field.setdefault('default_warnings', []).append('Unknown enum default: ' + text)
            elif kind == 'float':
                # Qt toFloat rounds to float32 BEFORE formatting with 6 digits.
                binary32 = struct.unpack('<f', struct.pack('<f', float(text)))[0]
                value = float(format(binary32, '.6e'))
            else:
                value = int(text, 10)
            vals.append(value)
        if not vals:
            vals = [0] * count
        default_blob.extend(struct.pack('<' + FORMATS[kind]*count, *vals))
        offset += WIDTHS[kind]*count
    result.update(id='0x%08x' % (obj_hash & 0xfffffffe), size=offset,
                  factory_payload_hex=default_blob.hex())
    return result


def load_schema(directory):
    objects, digest = [], hashlib.sha1()
    for path in sorted(Path(directory).glob('*.xml')):
        content = path.read_bytes().replace(b'\r\n', b'\n')
        digest.update(hashlib.sha1(content).hexdigest().encode('ascii'))
        for element in ET.fromstring(content).findall('object'):
            objects.append(parse_object(element))
    if len({o['id'] for o in objects}) != len(objects):
        raise ValueError('Duplicate UAVObject ID')
    return {'uavo_sha1': digest.hexdigest(), 'objects': objects,
            'warning': 'Factory defaults from upstream XML; not recovered user settings.'}


def decode_payload(obj, payload):
    if len(payload) != obj['size']:
        raise ValueError('Payload size does not match XML schema')
    fields = {}
    for field in obj['fields']:
        kind, count = field['type'], len(field['elements'])
        vals = struct.unpack_from('<' + FORMATS[kind]*count, payload, field['offset'])
        if kind == 'enum':
            vals = [field['options'][v] if v < len(field['options']) else {'invalid_enum': v} for v in vals]
        fields[field['name']] = vals[0] if count == 1 else dict(zip(field['elements'], vals))
    return fields


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('definitions', type=Path)
    p.add_argument('--out', type=Path, default=Path('analysis/baseline/uavo_schema.json'))
    args = p.parse_args()
    schema = load_schema(args.definitions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(schema, indent=2), encoding='utf-8')
    print('UAVO hash:', schema['uavo_sha1'], 'objects:', len(schema['objects']),
          'settings:', sum(o['settings'] for o in schema['objects']))


if __name__ == '__main__':
    main()
