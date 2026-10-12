# Firmware analysis and control-loop navigation

Run commands from the repository root. The tools operate on files; they do not
flash the controller.

## Verified memory map

Ranges below use an exclusive end address.

| Region | Range / value |
|---|---|
| Bootloader and board information | `[0x08000000, 0x08003000)` |
| Bootloader vector SP / reset instruction | `0x20000920` / `0x0800010C` |
| Application | `[0x08003000, 0x0801A698)` |
| Application vector SP / reset instruction | `0x2000023C` / `0x0800310C` |
| First OpFw descriptor | `[0x0801A698, 0x0801A6FC)` |
| Erased padding | `[0x0801A6FC, 0x0801FF9C)` |
| Second OpFw descriptor | `[0x0801FF9C, 0x08020000)` |
| MCU SRAM range | `[0x20000000, 0x20005000)` |

The stored reset-handler pointers have bit zero set for Thumb state. Clear it
to obtain an instruction address. Initial SP validation must accept four-byte
alignment: requiring eight-byte alignment would reject this real application
vector table. The original descriptor identifies commit prefix `bf68cc84`,
release `RELEASE-15.02.01` and board type/revision `04/02`.

## Fingerprinting and its limits

`tools/inspect_dump.py` scans plausible vector tables, printable ASCII,
erased regions, page entropy and OpFw descriptors. A string or vector pattern
is a lead; it does not identify a library conclusively. Startup vectors from
SPL and HAL projects may look alike. Likewise, absent protocol strings do not
prove a binary protocol is absent.

For an unknown image, follow reset through data initialization and main; check
whether SVC, PendSV and SysTick implement scheduler transitions. Look for task
creation, queue operations and blocking waits versus a repeated super-loop.
Confirm library families with source-to-binary comparisons, not the vector
table alone. Here the exact application rebuild resolves those uncertainties:
PIOS, STM32F1 SPL and FreeRTOS V8.0.1 are established by matching code.

Reference application handler instruction addresses are SVC `0x0800B188`,
PendSV `0x0800B1F4` and SysTick `0x0800B238`. The source reserves 0x240 bytes
for the IRQ stack, 0x100 for initialization, and 53*256 bytes for the FreeRTOS
heap; the tick rate is 1000 Hz. These values are not the flight-control loop
frequency or the sizes of every individual task stack.

## Import into Ghidra

Install Ghidra and a compatible Jython scripting extension if your Ghidra
distribution does not include it. These scripts use the Jython 2.7 API;
ordinary CPython or PyGhidra is not a drop-in runner. They have passed syntax
checks, but **have not been executed in Ghidra in this project**. Treat the
following as an integration procedure requiring verification.

In PowerShell, replace the installation path:

```powershell
$ghidraHome = 'C:\tools\ghidra'
New-Item -ItemType Directory -Force analysis/ghidra_projects | Out-Null
& "$ghidraHome\support\analyzeHeadless.bat" `
  "$PWD\analysis\ghidra_projects" Qimmiq `
  -import "$PWD\firmware.bin" `
  -loader BinaryLoader -loader-baseAddr 0x08000000 `
  -processor ARM:LE:32:Cortex `
  -scriptPath "$PWD\tools\ghidra" `
  -preScript PrepareSTM32.py `
  -postScript InventorySTM32.py "$PWD\analysis\ghidra_inventory.json"
```

`PrepareSTM32.py` creates SRAM/peripheral address spaces, marks Thumb state,
labels vector slots and seeds ISR functions. `InventorySTM32.py` exports
strings and references, MMIO literal candidates, resolved load/store accesses
and normalized function features. Its constant propagation is bounded to a
basic block. A literal peripheral address alone is not proof of a hardware
access, and unresolved indirect accesses remain possible.

After generating and verifying baseline symbols as described in the README,
run `ImportVerifiedSymbols.py` in the Ghidra Script Manager with this argument:

```text
<absolute-repository-path>/analysis/baseline/verified_symbols.json
```

It checks the application hash before importing labels and function names.
Review any function-boundary conflicts rather than treating the import as a
complete reconstruction of compiler debug types. Importing the rebuilt ELF
in a separate Ghidra project is also useful for its symbols and debug data.

## Map hardware connections

| Peripheral | Register base |
|---|---|
| GPIO A / B / C / D | `0x40010800` / `0x40010C00` / `0x40011000` / `0x40011400` |
| AFIO | `0x40010000` |
| RCC | `0x40021000` |
| SPI1 / SPI2 | `0x40013000` / `0x40003800` |
| I2C1 / I2C2 | `0x40005400` / `0x40005800` |
| TIM1 / TIM2 / TIM3 / TIM4 | `0x40012C00` / `0x40000000` / `0x40000400` / `0x40000800` |

GPIO CRL and CRH encode mode/configuration in four-bit fields. GPIO BSRR stores
identify set/reset masks; timer CCR writes identify candidate PWM outputs.
Combine those accesses with AFIO remapping, RCC clock enables, PIOS board
configuration tables and call sites. A timer channel alone does not identify
the physical motor connector, and a GPIO configuration table does not prove
that a component is installed. Record the source declaration, binary reference
and physical measurement separately.

Inspect the pinned target's `board_hw_defs.c`, firmware `pios_board.c` and PIOS
sensor drivers. Follow the actual initialization branch selected by board
revision and saved hardware settings. This is stronger evidence than searching
all linked driver names and assuming every listed sensor is used.

## Follow the flight-control data path

With byte-identical symbols, begin in these pinned source modules:

| Module | Investigation |
|---|---|
| `flight/modules/ManualControl` | Receiver scaling, arming and mode selection |
| `flight/modules/Stabilization` | Desired attitude/rate, inner and outer loops |
| `flight/libraries/math/pid.c` | PID updates, integral handling and limits |
| `flight/modules/Actuator` | Mixing, saturation and actuator outputs |

Follow receiver commands into the selected stabilization bank, then track
desired rate, gyro measurements, PID output and motor mixing. In attitude
control, an outer loop converts attitude error to a rate demand. In Rate
control, the stick-derived demand goes to the angular-rate loop. Centered
sticks do not demand level attitude in Rate mode.

For a different unmatched binary, useful clues include repeated three-axis
arithmetic, error subtraction, time-scaled integration, clamps, mode-dependent
branches, and mixer coefficient tables. Cortex-M3 has no hardware FPU: floating
point operations commonly call software helpers such as `__aeabi_fsub` and
`__aeabi_fmul`. There is no universal instruction signature for “Acro”. Check
data flow, units, scheduling and callers rather than one comparison opcode.

## Similarity matching for other revisions

This reference no longer requires guessing between Cleanflight, Baseflight and
OpenPilot: its exact OpenPilot application was reproduced. For another dump,
first compare descriptors and release metadata, then compile plausible targets
with their historical compiler and options. Feed original and reference ELFs
to BinDiff or export both through `InventorySTM32.py`:

```powershell
python tools/match_functions.py analysis/unknown-inventory.json analysis/reference-inventory.json
```

The tool ranks mnemonic/operand-type shingles and normalized block hashes with
a function-size filter. Results require manual validation. Small wrappers,
common library functions, inlining and compiler changes can create misleading
matches. Exact application equality is stronger evidence than a similarity
score, and is required by the verified-symbol export tool.

## Patching: prerequisites and boundaries

Prefer a controlled source change once the matching source is available.
First determine whether the existing Rate mode can be selected through saved
settings. A binary patch is a fallback for a localized, understood change.

For an in-place Thumb patch, preserve complete instruction boundaries: Thumb-2
instructions can occupy two or four bytes. Halfword alignment alone does not
prove a safe boundary. Review IT blocks, literal pools, branch ranges and every
incoming reference. A trampoline requires verified executable space, correct
Thumb-state handling, preserved registers/stack alignment and a return path
that accounts for displaced instructions and PC-relative operands. An erased
region is a candidate, not automatic permission to use it: check descriptors,
bootloader assumptions and update packaging.

`tools/patch_image.py` applies a JSON byte manifest to a new file, checking the
source SHA-256, size, original bytes, non-overlapping ranges and basic Thumb
alignment. It does **not** assemble code, validate its semantics, relocate
instructions, update integrity metadata or flash hardware. See its argument
help and `tests/test_re_tools.py` for manifest validation examples. No actual
flight-mode patch manifest is provided at this checkpoint.

If application bytes change, regenerate OpenPilot integrity metadata using
the verified upstream format and review both descriptor copies and image
layout. The exact-image reconstruction tool intentionally refuses modified
applications; it is a baseline check, not a modified firmware packager.

## Next evidence to collect

- A compatible settings export or verified external-flash capture.
- Photographs and measured SWD/SPI connections for the exact board revision.
- Actual switch-position mappings and stabilization modes.
- Successful Ghidra execution, with version and script logs.
- A recoverable bench procedure before any experimental hardware write.

No new firmware has been flashed or tested in flight. Keep that distinction
when sharing conclusions or instructions with other owners.
