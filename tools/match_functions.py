"""Rank candidates from InventorySTM32 JSON exports; never rename automatically."""
import argparse
import json
from pathlib import Path


def rank(left, right, top=3):
    output = []
    for f in left:
        if f['instruction_count'] < 12:
            continue
        a = set(f['shingles_5'])
        if not a:
            continue
        candidates = []
        for g in right:
            n, m = f['instruction_count'], g['instruction_count']
            if min(n, m) / max(n, m) < 0.5:
                continue
            b = set(g['shingles_5'])
            similarity = len(a & b) / len(a | b) if b else 0
            exact_blocks = len(set(f['normalized_blocks']) & set(g['normalized_blocks']))
            if similarity >= 0.3:
                candidates.append({'name': g['name'], 'address': g['address'],
                                   'jaccard': round(similarity, 4),
                                   'shared_block_hashes': exact_blocks,
                                   'instruction_count': m})
        candidates.sort(key=lambda c: (c['jaccard'], c['shared_block_hashes']), reverse=True)
        if candidates:
            output.append({'unknown': f['address'], 'current_name': f['name'],
                           'candidates': candidates[:top], 'status': 'manual_validation_required'})
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('unknown', type=Path)
    p.add_argument('reference', type=Path)
    p.add_argument('--out', type=Path, default=Path('analysis/function_matches.json'))
    args = p.parse_args()
    result = rank(json.loads(args.unknown.read_text())['functions'],
                  json.loads(args.reference.read_text())['functions'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(len(result), 'functions with candidate matches; output:', args.out)


if __name__ == '__main__':
    main()
