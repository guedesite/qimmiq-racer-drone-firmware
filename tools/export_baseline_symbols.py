"""Export symbols only when the reference application equals the original dump."""
import argparse
import json
import re
from pathlib import Path
from compare_baseline import compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dump', type=Path)
    p.add_argument('application', type=Path)
    p.add_argument('nm_symbols', type=Path)
    p.add_argument('--out', type=Path, default=Path('analysis/baseline/verified_symbols.json'))
    args = p.parse_args()
    evidence = compare(args.dump.read_bytes(), args.application.read_bytes())
    if not evidence['identical']:
        raise ValueError('Application mismatch: symbol addresses are not proven')
    symbols = []
    for line in args.nm_symbols.read_text(encoding='utf-8').splitlines():
        match = re.match(r'^([0-9a-fA-F]+)(?:\s+([0-9a-fA-F]+))?\s+([A-Za-z])\s+(.+)$', line)
        if not match:
            continue
        address, size, kind, name = match.groups()
        address = int(address, 16)
        if not (0x08003000 <= address < 0x0801a698 or 0x20000000 <= address < 0x20005000):
            continue
        if name.startswith('$'):
            continue  # ARM mapping symbols are not user-facing labels.
        symbols.append({'address': hex(address), 'size': int(size, 16) if size else 0,
                        'kind': kind, 'name': name})
    report = {'application_base': evidence['application_base'], 'application_size': evidence['compiled_size'],
              'application_sha1': evidence['compiled_sha1'], 'verified_byte_identical': True,
              'symbols': symbols}
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Verified symbols:', len(symbols), 'functions with sizes:',
          sum(s['kind'] in ('t', 'T') and s['size'] > 0 for s in symbols))


if __name__ == '__main__':
    main()
