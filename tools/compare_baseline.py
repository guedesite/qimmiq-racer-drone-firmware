"""Compare a linked OpenPilot application against the extracted flash region."""
import argparse
import hashlib
import json
from pathlib import Path
from inspect_dump import inspect


def compare(original, compiled, base=0x08000000, application_base=0x08003000):
    inventory = inspect(original, base)
    ranges = [r for d in inventory['openpilot_descriptors'] for r in d['verified_hash_ranges']
              if int(r['start'], 16) == application_base]
    if not ranges:
        raise ValueError('No verified descriptor covers the selected application')
    end = int(ranges[0]['end_exclusive'], 16)
    reference = original[application_base-base:end-base]
    common = min(len(reference), len(compiled))
    runs = []
    start = None
    for i in range(common):
        if reference[i] != compiled[i] and start is None:
            start = i
        elif reference[i] == compiled[i] and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, common))
    different = sum(b-a for a,b in runs) + abs(len(reference)-len(compiled))
    return {'application_base': hex(application_base), 'original_end_exclusive': hex(end),
            'original_size': len(reference), 'compiled_size': len(compiled),
            'original_sha1': hashlib.sha1(reference).hexdigest(),
            'compiled_sha1': hashlib.sha1(compiled).hexdigest(),
            'identical': reference == compiled, 'different_bytes': different,
            'difference_run_count': len(runs),
            'first_difference_runs': [{'start': hex(application_base+a), 'end_exclusive': hex(application_base+b),
                                       'length': b-a} for a,b in runs[:100]],
            'scope': 'Application bytes only; bootloader, descriptors, external settings and option bytes excluded.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dump', type=Path)
    p.add_argument('compiled_application_bin', type=Path)
    p.add_argument('--out', type=Path, default=Path('analysis/baseline/comparison.json'))
    args = p.parse_args()
    result = compare(args.dump.read_bytes(), args.compiled_application_bin.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Identical application:', result['identical'])
    print('Sizes:', result['original_size'], result['compiled_size'])
    print('SHA1:', result['original_sha1'], result['compiled_sha1'])
    print('Different bytes:', result['different_bytes'])


if __name__ == '__main__':
    main()
