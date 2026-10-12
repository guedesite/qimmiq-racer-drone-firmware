# Import exact baseline symbols into an existing raw dump project.
# @category STM32.RE
# Argument: verified_symbols.json
# Jython 2.7. Refuses to import if application bytes differ.
import hashlib
import json
from ghidra.program.model.symbol import SourceType

args = getScriptArgs()
if len(args) != 1:
    raise RuntimeError('Argument required: verified_symbols.json')
with open(args[0], 'r') as stream:
    report = json.load(stream)
if report.get('verified_byte_identical') is not True:
    raise RuntimeError('Symbol export has no verified baseline')
base = int(report['application_base'], 16)
size = int(report['application_size'])
memory = currentProgram.getMemory()
raw = bytearray(memory.getByte(toAddr(base+i)) & 255 for i in range(size))
if hashlib.sha1(bytes(raw)).hexdigest() != report['application_sha1']:
    raise RuntimeError('Current program does not match the baseline application')
renamed, conflicts = 0, []
for symbol in report['symbols']:
    monitor.checkCancelled()
    address = toAddr(int(symbol['address'], 16))
    if memory.getBlock(address) is None:
        continue
    name = symbol['name']
    createLabel(address, name, False, SourceType.IMPORTED)
    if symbol['kind'] not in ('t', 'T') or symbol['size'] == 0:
        continue
    function = getFunctionAt(address)
    if function is None:
        containing = getFunctionContaining(address)
        if containing is not None:
            conflicts.append(str(address) + ' ' + name + ': inside ' + containing.getName())
            continue
        disassemble(address)
        function = createFunction(address, name)
    if function is not None:
        function.setName(name, SourceType.IMPORTED)
        renamed += 1
print('Imported %d function names. %d boundary conflicts require review.' % (renamed, len(conflicts)))
for conflict in conflicts:
    print(conflict)
