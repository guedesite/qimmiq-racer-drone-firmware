# Prepare a raw STM32F103CB dump BEFORE auto-analysis.
# @category STM32.RE
# Jython 2.7 script (Ghidra's optional Jython extension).
from java.math import BigInteger
from ghidra.program.model.symbol import SourceType
import struct

BASE = 0x08000000
CORE = ('Initial_SP Reset NMI HardFault MemManage BusFault UsageFault Reserved7 '
        'Reserved8 Reserved9 Reserved10 SVC DebugMon Reserved13 PendSV SysTick').split()
IRQ = ('WWDG PVD TAMPER RTC FLASH RCC EXTI0 EXTI1 EXTI2 EXTI3 EXTI4 '
       'DMA1_Channel1 DMA1_Channel2 DMA1_Channel3 DMA1_Channel4 DMA1_Channel5 '
       'DMA1_Channel6 DMA1_Channel7 ADC1_2 USB_HP_CAN_TX USB_LP_CAN_RX0 '
       'CAN_RX1 CAN_SCE EXTI9_5 TIM1_BRK TIM1_UP TIM1_TRG_COM TIM1_CC '
       'TIM2 TIM3 TIM4 I2C1_EV I2C1_ER I2C2_EV I2C2_ER SPI1 SPI2 '
       'USART1 USART2 USART3 EXTI15_10 RTCAlarm USBWakeUp').split()
mem = currentProgram.getMemory()
block = mem.getBlock(toAddr(BASE))
if block is None or block.getStart().getOffset() != BASE:
    raise RuntimeError('Import raw binary at 0x08000000 first.')
size = int(block.getSize())
if size != 131072:
    raise RuntimeError('This pre-script expects the complete 128 KiB raw dump.')

for name, start, length in [('SRAM', 0x20000000, 0x5000),
                             ('PERIPHERALS', 0x40000000, 0x24000),
                             ('PPB', 0xe000e000, 0x2000)]:
    if mem.getBlock(toAddr(start)) is None:
        b = mem.createUninitializedBlock(name, toAddr(start), length, False)
        b.setRead(True)
        b.setWrite(True)
        b.setExecute(False)
block.setExecute(True)
block.setWrite(False)
tmode = currentProgram.getRegister('TMode')
if tmode is None:
    raise RuntimeError('Use processor ARM:LE:32:Cortex.')
currentProgram.getProgramContext().setValue(tmode, block.getStart(), block.getEnd(), BigInteger.ONE)

def word(off):
    return mem.getInt(toAddr(BASE + off)) & 0xffffffff

def valid_handler(value):
    return value & 1 and BASE <= (value & ~1) < BASE + size

for off in range(0, size - 236 + 1, 4):
    monitor.checkCancelled()
    sp, reset = word(off), word(off + 4)
    if not (0x20000000 < sp <= 0x20005000 and sp % 4 == 0 and valid_handler(reset)):
        continue
    words = [word(off + i * 4) for i in range(59)]
    active = [w for i, w in enumerate(words) if i and i not in (7, 8, 9, 10, 13)]
    if sum(bool(valid_handler(w)) for w in active) < 8:
        continue
    if sum(w not in (0, 0xffffffff) and not valid_handler(w) for w in active) > 2:
        continue
    prefix = 'vt_%08x_' % (BASE + off)
    createLabel(toAddr(BASE + off), prefix + 'table', False, SourceType.USER_DEFINED)
    for i, name in enumerate(CORE + IRQ):
        slot = toAddr(BASE + off + 4 * i)
        if getDataAt(slot) is None and getInstructionContaining(slot) is None:
            createDWord(slot)
        setEOLComment(slot, prefix + name + ': 0x%08x' % words[i])
        if i and valid_handler(words[i]):
            target = toAddr(words[i] & ~1)
            createLabel(target, prefix + name, False, SourceType.USER_DEFINED)
            currentProgram.getSymbolTable().addExternalEntryPoint(target)
            disassemble(target)
            if getFunctionAt(target) is None:
                createFunction(target, prefix + name)
    print('Vector candidate at 0x%08x, SP=0x%08x' % (BASE + off, sp))
