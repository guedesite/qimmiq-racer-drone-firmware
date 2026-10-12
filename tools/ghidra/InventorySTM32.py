# Export strings, vector tables, MMIO accesses and normalized function features.
# @category STM32.RE
# Arguments: output.json [base_address] [size]
# Jython 2.7; bounded constant propagation inside each basic block only.
import hashlib
import json
import os
import re
from ghidra.program.model.block import BasicBlockModel
from ghidra.program.model.pcode import PcodeOp

args = getScriptArgs()
BASE = int(args[1], 0) if len(args) > 1 else 0x08000000
SIZE = int(args[2], 0) if len(args) > 2 else 0x20000
mem = currentProgram.getMemory()
listing = currentProgram.getListing()
raw = bytearray([255]) * SIZE
flash_blocks = [b for b in mem.getBlocks() if b.isInitialized()
                and b.getStart().getOffset() < BASE+SIZE and b.getEnd().getOffset() >= BASE
                and b.getStart().getAddressSpace() == toAddr(BASE).getAddressSpace()]
if not flash_blocks:
    raise RuntimeError('No initialized flash blocks in selected range')
for block in flash_blocks:
    for address in range(max(BASE, block.getStart().getOffset()),
                         min(BASE+SIZE, block.getEnd().getOffset()+1)):
        raw[address-BASE] = mem.getByte(toAddr(address)) & 255
def hx(value):
    return '0x%08x' % value
def u32(off):
    return sum(raw[off+i] << (8*i) for i in range(4))
def refs(addr):
    return [str(r.getFromAddress()) for r in getReferencesTo(addr)]

GPIO = {0: 'CRL', 4: 'CRH', 8: 'IDR', 12: 'ODR', 16: 'BSRR', 20: 'BRR', 24: 'LCKR'}
SPI = {0: 'CR1', 4: 'CR2', 8: 'SR', 12: 'DR', 16: 'CRCPR', 20: 'RXCRCR', 24: 'TXCRCR'}
I2C = {0: 'CR1', 4: 'CR2', 8: 'OAR1', 12: 'OAR2', 16: 'DR', 20: 'SR1',
       24: 'SR2', 28: 'CCR', 32: 'TRISE'}
TIM = {0: 'CR1', 4: 'CR2', 8: 'SMCR', 12: 'DIER', 16: 'SR', 20: 'EGR',
       24: 'CCMR1', 28: 'CCMR2', 32: 'CCER', 36: 'CNT', 40: 'PSC',
       44: 'ARR', 48: 'RCR', 52: 'CCR1', 56: 'CCR2', 60: 'CCR3', 64: 'CCR4', 68: 'BDTR'}
RCC = {0: 'CR', 4: 'CFGR', 8: 'CIR', 12: 'APB2RSTR', 16: 'APB1RSTR',
       20: 'AHBENR', 24: 'APB2ENR', 28: 'APB1ENR'}
UNITS = [('AFIO', 0x40010000, {0: 'EVCR', 4: 'MAPR', 28: 'MAPR2'}),
         ('GPIOA', 0x40010800, GPIO), ('GPIOB', 0x40010c00, GPIO),
         ('GPIOC', 0x40011000, GPIO), ('GPIOD', 0x40011400, GPIO),
         ('SPI1', 0x40013000, SPI), ('SPI2', 0x40003800, SPI),
         ('I2C1', 0x40005400, I2C), ('I2C2', 0x40005800, I2C),
         ('TIM1', 0x40012c00, TIM), ('TIM2', 0x40000000, TIM),
         ('TIM3', 0x40000400, TIM), ('TIM4', 0x40000800, TIM),
         ('RCC', 0x40021000, RCC), ('FLASH', 0x40022000, {}),
         ('CRC', 0x40023000, {}), ('USART1', 0x40013800, {}),
         ('USART2', 0x40004400, {}), ('USART3', 0x40004800, {}),
         ('DMA1', 0x40020000, {})]
def peripheral(value):
    if value == 0xe000ed08:
        return 'SCB.VTOR'
    for name, base, registers in UNITS:
        if base <= value < base + 0x400:
            offset = value - base
            return name + '.' + registers.get(offset, '+0x%x' % offset)
    if 0xe000e000 <= value < 0xe0010000:
        return 'PPB.+0x%x' % (value-0xe000e000)
    return None

def key(v):
    return (str(v.getAddress().getAddressSpace().getName()), v.getOffset(), v.getSize())
def value(v, state):
    return v.getOffset() if v.isConstant() else state.get(key(v))
def flash_read(address, size):
    off = address - BASE
    if 0 <= off and off+size <= SIZE:
        return sum(raw[off+i] << (8*i) for i in range(size))
    return None
def resolve(op, state):
    a = [value(op.getInput(i), state) for i in range(op.getNumInputs())]
    code = op.getOpcode()
    if code in (PcodeOp.COPY, PcodeOp.CAST, PcodeOp.INT_ZEXT) and a:
        return a[0]
    if code == PcodeOp.LOAD and a[1] is not None:
        return flash_read(a[1], op.getOutput().getSize())
    if any(x is None for x in a):
        return None
    if code == PcodeOp.INT_SEXT:
        bits = 8*op.getInput(0).getSize()
        return a[0] - (1 << bits) if a[0] & (1 << (bits-1)) else a[0]
    if code == PcodeOp.INT_ADD: return a[0] + a[1]
    if code == PcodeOp.INT_SUB: return a[0] - a[1]
    if code == PcodeOp.INT_MULT: return a[0] * a[1]
    if code == PcodeOp.INT_AND: return a[0] & a[1]
    if code == PcodeOp.INT_OR: return a[0] | a[1]
    if code == PcodeOp.INT_XOR: return a[0] ^ a[1]
    if code == PcodeOp.INT_LEFT: return a[0] << a[1] if a[1] < 64 else 0
    if code == PcodeOp.INT_RIGHT: return a[0] >> a[1] if a[1] < 64 else 0
    if code == PcodeOp.SUBPIECE: return a[0] >> (8*a[1])
    if code == PcodeOp.PIECE: return (a[0] << (8*op.getInput(1).getSize())) | a[1]
    return None

vectors = []
for off in range(0, SIZE-236+1, 4):
    sp, reset = u32(off), u32(off+4)
    valid = lambda w: bool(w & 1) and BASE <= (w & ~1) < BASE+SIZE
    if not (0x20000000 < sp <= 0x20005000 and sp % 4 == 0 and valid(reset)): continue
    words = [u32(off+4*i) for i in range(59)]
    active = [w for i, w in enumerate(words) if i and i not in (7,8,9,10,13)]
    if sum(valid(w) for w in active) >= 8 and sum(w not in (0,0xffffffff) and not valid(w) for w in active) <= 2:
        vectors.append({'address': hx(BASE+off), 'entries': [hx(w) for w in words]})

strings = []
for match in re.finditer(b'[\x20-\x7e]{6,}', bytes(raw)):
    address = BASE+match.start()
    strings.append({'address': hx(address), 'text': match.group().decode('ascii'),
                    'nul_terminated': match.end() < SIZE and raw[match.end()] == 0,
                    'xrefs': refs(toAddr(address))})

literal_candidates = []
for off in range(0, SIZE-3, 4):
    val = u32(off)
    unit = peripheral(val)
    if unit:
        literal_candidates.append({'address': hx(BASE+off), 'value': hx(val),
                                   'register': unit, 'xrefs': refs(toAddr(BASE+off)),
                                   'evidence': 'raw_constant_only'})

accesses, functions, errors = [], [], []
model = BasicBlockModel(currentProgram)
for fun in currentProgram.getFunctionManager().getFunctions(True):
    monitor.checkCancelled()
    if fun.isExternal(): continue
    tokens, normalized_blocks = [], []
    blocks = model.getCodeBlocksContaining(fun.getBody(), monitor)
    while blocks.hasNext():
        bb = blocks.next()
        state, block_tokens = {}, []
        instructions = listing.getInstructions(bb, True)
        while instructions.hasNext():
            ins = instructions.next()
            if not fun.getBody().contains(ins.getAddress()): continue
            # Unique temporaries are local to the current instruction.
            state = dict((k,v) for k,v in state.items() if k[0] != 'unique')
            # Operand TYPES retained; addresses/immediates/register identities omitted.
            token = ins.getMnemonicString().lower() + ':' + ','.join(
                str(ins.getOperandType(i)) for i in range(ins.getNumOperands()))
            tokens.append(token)
            block_tokens.append(token)
            for op in ins.getPcode():
                try:
                    if op.getOpcode() in (PcodeOp.LOAD, PcodeOp.STORE):
                        addr = value(op.getInput(1), state)
                        unit = peripheral(addr) if addr is not None else None
                        if unit:
                            store = op.getOpcode() == PcodeOp.STORE
                            val = value(op.getInput(2), state) if store else None
                            record = {'instruction': str(ins.getAddress()), 'function': fun.getName(),
                                      'function_address': str(fun.getEntryPoint()),
                                      'operation': 'write' if store else 'read', 'register': unit,
                                      'address': hx(addr), 'value': hx(val) if val is not None else None,
                                      'width': op.getInput(2).getSize() if store else op.getOutput().getSize(),
                                      'evidence': 'basic_block_constant_propagation'}
                            if store and val is not None and unit.startswith('GPIO'):
                                if unit.endswith(('.CRL', '.CRH')) and record['width'] == 4:
                                    first = 8 if unit.endswith('.CRH') else 0
                                    record['pin_nibbles'] = {str(first+i): (val >> (4*i)) & 15 for i in range(8)}
                                elif unit.endswith('.BSRR'):
                                    record['pins_set'] = [i for i in range(16) if val & (1 << i)]
                                    record['pins_reset'] = [i for i in range(16) if val & (1 << (i+16))]
                            accesses.append(record)
                    out = op.getOutput()
                    if out is not None:
                        resolved = resolve(op, state)
                        state.pop(key(out), None)
                        if resolved is not None:
                            state[key(out)] = resolved & ((1 << (8*out.getSize())) - 1)
                    if op.getOpcode() in (PcodeOp.CALL, PcodeOp.CALLIND, PcodeOp.CALLOTHER):
                        state.clear()
                except Exception as error:
                    errors.append({'instruction': str(ins.getAddress()), 'error': str(error)})
                    state.clear()
            if ins.getFlowType().isCall(): state.clear()
        normalized_blocks.append(hashlib.sha256('|'.join(block_tokens).encode('ascii')).hexdigest())
    shingles = sorted(set(hashlib.sha256('|'.join(tokens[i:i+5]).encode('ascii')).hexdigest()
                          for i in range(max(0, len(tokens)-4))))
    functions.append({'address': str(fun.getEntryPoint()), 'name': fun.getName(),
                      'instruction_count': len(tokens), 'block_count': len(normalized_blocks),
                      'normalized_blocks': normalized_blocks, 'shingles_5': shingles,
                      'callers': refs(fun.getEntryPoint())})

output = args[0] if args else 'stm32_inventory.json'
parent = os.path.dirname(os.path.abspath(output))
if not os.path.isdir(parent): os.makedirs(parent)
with open(output, 'w') as stream:
    json.dump({'program': currentProgram.getName(), 'vectors': vectors, 'strings': strings,
               'mmio_literals': literal_candidates, 'mmio_accesses': accesses,
               'functions': functions, 'propagation_errors': errors,
               'limits': 'No inter-block/interprocedural propagation; unresolved accesses omitted. '
                         'GPIO pin roles require AFIO, package and electrical confirmation.'}, stream, indent=2)
print('Exported %d functions and %d resolved MMIO accesses to %s' % (len(functions), len(accesses), output))
