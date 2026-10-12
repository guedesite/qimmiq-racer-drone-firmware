"""Reconstruct the exact original flash using compiled application and preserved bootloader."""
import argparse
import hashlib
import json
from pathlib import Path
from inspect_dump import inspect


def reconstruct(original, application, descriptor):
    inventory = inspect(original)
    app_start = 0x3000
    if len(original) != 0x20000 or len(descriptor) != 100:
        raise ValueError('Expected complete 128 KiB dump and 100-byte descriptor')
    expected_sha1 = inventory['openpilot_descriptors'][0]['firmware_sha1']
    if hashlib.sha1(application).hexdigest() != expected_sha1:
        raise ValueError('Compiled application does not match original descriptor')
    first_descriptor = app_start + len(application)
    descriptor_offsets = [int(d['address'], 16)-0x08000000 for d in inventory['openpilot_descriptors']]
    if descriptor_offsets != [first_descriptor, len(original)-100]:
        raise ValueError('Descriptor placement does not match the verified original layout')
    if any(original[o:o+100] != descriptor for o in descriptor_offsets):
        raise ValueError('Compiled descriptor differs from original')
    result = bytearray(b'\xff' * len(original))
    # Preserve existing bootloader and board-info bytes rather than substitute a different build.
    result[:app_start] = original[:app_start]
    result[app_start:first_descriptor] = application
    for offset in descriptor_offsets:
        result[offset:offset+100] = descriptor
    if result != original:
        raise ValueError('Reconstructed image differs; refusing to call it an exact baseline')
    return bytes(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dump', type=Path)
    p.add_argument('application', type=Path)
    p.add_argument('descriptor', type=Path)
    p.add_argument('--compiled-full', type=Path)
    p.add_argument('--out', type=Path, default=Path('analysis/baseline/firmware-1for1.bin'))
    args = p.parse_args()
    original = args.dump.read_bytes()
    output = reconstruct(original, args.application.read_bytes(), args.descriptor.read_bytes())
    if args.out.resolve() == args.dump.resolve():
        raise ValueError('Never overwrite original dump')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        if args.out.read_bytes() != output:
            raise ValueError('Output exists with different bytes')
    else:
        with args.out.open('xb') as stream:
            stream.write(output)
    report = {'exact_original_flash_reconstructed': True, 'size': len(output),
              'sha256': hashlib.sha256(output).hexdigest(),
              'recompiled': ['application', 'OpFw descriptors'],
              'preserved_from_dump': ['bootloader and BD_INFO: [0x08000000, 0x08003000)'],
              'padding': '0xff', 'external_settings_recovered': False}
    if args.compiled_full:
        full = args.compiled_full.read_bytes()
        spans = [('bootloader_and_board_info', 0, 0x3000), ('application', 0x3000, 0x1a698),
                 ('first_descriptor', 0x1a698, 0x1a6fc), ('padding', 0x1a6fc, 0x1ff9c),
                 ('last_descriptor', 0x1ff9c, 0x20000)]
        report['fully_recompiled_image_comparison'] = {
            'size': len(full), 'identical': full == original,
            'regions': {name: {'identical': full[start:end] == original[start:end],
                              'different_bytes': sum(a != b for a,b in zip(full[start:end], original[start:end]))
                              + abs(len(full[start:end])-len(original[start:end]))}
                        for name,start,end in spans}}
    args.out.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Exact flash image:', args.out)
    print('SHA256:', report['sha256'])
    print('Application recompiled; original bootloader and board info preserved.')


if __name__ == '__main__':
    main()
