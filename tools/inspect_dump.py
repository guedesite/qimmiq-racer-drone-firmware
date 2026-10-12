"""Read-only STM32F103CB inventory; Python 3, standard library only."""
import argparse
import hashlib
import json
import math
import re
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CORE = ['Initial_SP', 'Reset', 'NMI', 'HardFault', 'MemManage', 'BusFault',
        'UsageFault', 'Reserved7', 'Reserved8', 'Reserved9', 'Reserved10',
        'SVC', 'DebugMon', 'Reserved13', 'PendSV', 'SysTick']
IRQ = ('WWDG PVD TAMPER RTC FLASH RCC EXTI0 EXTI1 EXTI2 EXTI3 EXTI4 '
       'DMA1_Channel1 DMA1_Channel2 DMA1_Channel3 DMA1_Channel4 DMA1_Channel5 '
       'DMA1_Channel6 DMA1_Channel7 ADC1_2 USB_HP_CAN_TX USB_LP_CAN_RX0 '
       'CAN_RX1 CAN_SCE EXTI9_5 TIM1_BRK TIM1_UP TIM1_TRG_COM TIM1_CC '
       'TIM2 TIM3 TIM4 I2C1_EV I2C1_ER I2C2_EV I2C2_ER SPI1 SPI2 '
       'USART1 USART2 USART3 EXTI15_10 RTCAlarm USBWakeUp').split()
NAMES = CORE + IRQ
RESERVED = {7, 8, 9, 10, 13}
BASE = 0x08000000


def vector_candidates(data, base=BASE):
    result = []
    for off in range(0, len(data) - 4 * len(NAMES) + 1, 4):
        words = struct.unpack_from('<59I', data, off)
        sp, reset = words[:2]
        valid = lambda w: bool(w & 1) and base <= (w & ~1) < base + len(data)
        if not (0x20000000 < sp <= 0x20005000 and sp % 4 == 0 and valid(reset)):
            continue
        active = [w for i, w in enumerate(words[1:], 1) if i not in RESERVED]
        handlers = sum(valid(w) for w in active)
        invalid = sum(w not in (0, 0xffffffff) and not valid(w) for w in active)
        if handlers < 8 or invalid > 2:
            continue
        result.append({'address': hex(base + off), 'offset': off,
                       'handlers_in_flash': handlers, 'invalid_entries': invalid,
                       'aligned_0x200': (base + off) % 0x200 == 0,
                       'sp_aligned_8': sp % 8 == 0,
                       'entries': [{'index': i, 'name': NAMES[i], 'value': hex(w),
                                    'target': hex(w & ~1) if i and valid(w) else None}
                                   for i, w in enumerate(words)]})
    return result


def inspect(data, base=BASE):
    strings = [{'address': hex(base + m.start()), 'text': m.group().decode('ascii'),
                'nul_terminated': m.end() < len(data) and data[m.end()] == 0}
               for m in re.finditer(rb'[\x20-\x7e]{6,}', data)]
    keywords = re.compile(r'cleanflight|baseflight|openpilot|librepilot|RELEASE|'
                          r'OpFw|FreeRTOS|assert|\.c\b|MAV|MSP|SBUS|PID|gyro', re.I)
    erased = [{'start': hex(base + m.start()), 'end_exclusive': hex(base + m.end()),
               'length': m.end() - m.start(), 'status': 'candidate_only'}
              for m in re.finditer(rb'\xff{256,}', data)]
    pages = []
    for off in range(0, len(data), 1024):
        page = data[off:off+1024]
        counts = Counter(page)
        entropy = -sum((n / len(page)) * math.log2(n / len(page)) for n in counts.values())
        pages.append({'address': hex(base+off), 'entropy': round(entropy, 3),
                      'ff_fraction': round(page.count(255) / len(page), 3)})
    descriptors = []
    tables = vector_candidates(data, base)
    for match in re.finditer(b'OpFw', data):
        off = match.start()
        if off + 100 > len(data):
            continue
        blob = data[off:off+100]
        commit, timestamp = struct.unpack_from('<II', blob, 4)
        stored_hash = blob[40:60].hex()
        hash_matches = []
        # Verify possible firmware starts and earlier duplicate descriptor boundaries.
        boundaries = sorted({off} | {m.start() for m in re.finditer(b'OpFw', data) if m.start() <= off})
        for table in tables:
            for end in boundaries:
                start = table['offset']
                if start < end and hashlib.sha1(data[start:end]).hexdigest() == stored_hash:
                    hash_matches.append({'start': hex(base+start), 'end_exclusive': hex(base+end)})
        descriptors.append({'address': hex(base+off), 'length': 100,
                            'commit_prefix': '%08x' % commit,
                            'timestamp_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                            'board_type': blob[12], 'board_revision': blob[13],
                            'tag': blob[14:40].split(b'\0')[0].decode('ascii', errors='replace'),
                            'firmware_sha1': stored_hash, 'uavo_sha1': blob[60:80].hex(),
                            'verified_hash_ranges': hash_matches})
    return {'size': len(data), 'base': hex(base), 'sha256': hashlib.sha256(data).hexdigest(),
            'vector_candidates': tables, 'openpilot_descriptors': descriptors, 'strings': strings,
            'keyword_strings': [s for s in strings if keywords.search(s['text'])],
            'erased_runs': erased, 'pages_1k': pages,
            'warning': 'Printable instruction bytes and erased flash are not semantic evidence.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--base', type=lambda s: int(s, 0), default=BASE)
    parser.add_argument('--out', type=Path, default=Path('analysis/raw_inventory.json'))
    args = parser.parse_args()
    report = inspect(args.dump.read_bytes(), args.base)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SHA256:', report['sha256'])
    for table in report['vector_candidates']:
        print('Vectors:', table['address'], 'SP:', table['entries'][0]['value'],
              'Reset:', table['entries'][1]['value'])
    for s in report['keyword_strings']:
        print(s['address'], repr(s['text']))
    for descriptor in report['openpilot_descriptors']:
        print('OpFw:', descriptor['address'], descriptor['tag'], descriptor['commit_prefix'],
              'verified:', descriptor['verified_hash_ranges'])
    print('Inventory:', args.out)


if __name__ == '__main__':
    main()
