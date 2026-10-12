# Reproduction and saved settings

## What “one for one” means here

The pinned OpenPilot application was recompiled and directly compared against
the internal-flash dump: all 95896 application bytes match. Both 100-byte OpFw
descriptors match too. This establishes the compiled application, including
its drivers and compiled defaults, rather than merely a similar source tree.

The full upstream `ef_coptercontrol` image is different: 11181 bytes differ in
the first 12 KiB, and its packaging omits the intermediate 100-byte descriptor.
The reconstructed exact image therefore retains the original bootloader and
BD_INFO. It is not a byte-identical recompilation of the bootloader.

The chip's option bytes, backup registers, external memory and runtime state
are separate from the 128 KiB dump. A matching internal image does not establish
an identical complete controller state or guarantee an untested modification.

## Build provenance

| Component | Reference |
|---|---|
| Source | `bf68cc84d471feb0d9346f40f012e6c8e4de4bbb` |
| Reported release | `RELEASE-15.02.01` |
| Application target | `fw_coptercontrol` |
| ARM compiler | GNU ARM Embedded `4.9-2014-q4-major` |
| Historical scripts | Locally built Python 2.7.18 |
| Host object generator | Qt 5.15.13 in the verified build |
| RTOS | FreeRTOS V8.0.1 |
| HAL layer | PIOS over STM32F1 SPL |

Qt is used by the host generator, not as firmware code. Its generated output
was checked independently: the 104 object IDs match the generated headers and
the cumulative XML SHA-1 matches the descriptor. Application equality is the
final check on the build, regardless of host tool version differences.

The source archive is downloaded from the pinned LibrePilot commit. Its
SHA-256 is `fc869ebb66c9ba2231ce4cbd690b36d6fef6797707e1d62ec0a5a7110f962b2c`.
The generated `version-info.json` supplies the descriptor's original revision,
release and timestamp for an archive build without Git history. It does not
independently establish the vendor's original build machine or history.

See [the README build tutorial](../README.md#3-download-the-exact-source-and-tools)
for dependencies and commands. The wrapper stores Python 2 and the ARM compiler
under `/tmp/qimmiq-openpilot-bf68cc84-toolchains` inside WSL. If that temporary
directory disappears, the next build recreates the tools from cached archives.
Compilation logs stay in `analysis/baseline/` and are ignored by Git.

## Reconstruct the full image

Run these PowerShell commands from the repository root **after the application
comparison succeeds**:

```powershell
wsl -d Ubuntu -- bash tools/build_baseline.sh --full
$sourceRoot = 'analysis/baseline/LibrePilot-bf68cc84d471feb0d9346f40f012e6c8e4de4bbb'
$buildRoot = "$sourceRoot/build/fw_coptercontrol"
python tools/reconstruct_baseline.py firmware.bin "$buildRoot/fw_coptercontrol.bin" "$buildRoot/fw_coptercontrol.bin.firmware_info.bin" --compiled-full "$sourceRoot/build/ef_coptercontrol/ef_coptercontrol.bin"
Get-FileHash analysis/baseline/firmware-1for1.bin -Algorithm SHA256
```

The descriptor input is `fw_coptercontrol.bin.firmware_info.bin`, exactly
100 bytes. The reconstruction script checks the application hash, descriptor
copies, placement and final byte equality before accepting the result. It
will not overwrite the original dump or an existing different output.

The report identifies which regions were rebuilt and which were preserved.
Do not use the upstream full image as a replacement for the original
bootloader simply because its application matches.

## Three kinds of parameters

| Kind | Examples | How to preserve or verify |
|---|---|---|
| Compiled configuration | PIOS tables, drivers, linker layout, RTOS configuration | Exact build comparison |
| Compiled defaults | XML defaults and generated `SetDefaults` payloads | Schema plus exact build comparison |
| Saved configuration | Calibration, radio mapping, PID banks, mixer, flight mode selection | GCS export or verified external-memory dump |

`analysis/baseline/uavo_schema.json` describes 104 UAVObjects, including 35
settings objects. The total payload size across all 104 definitions is 4228
bytes. Its `factory_payload_hex` fields describe defaults, **not values read
from the drone**.

The reference CC3D implementation uses JEDEC SPI flash and PIOS LogFS for
persistence. Its reference geometry is 2 MiB, 64 KiB arenas and 256-byte slots.
Application equality establishes the code; it does not independently identify
the physical memory part or prove all board connections. Confirm the JEDEC
identity, capacity and capture offset before using those decoder assumptions.

## Recover the external settings

1. Export settings through an already compatible, working GCS connection if
   possible. Save the original export before running any setup wizard.
2. Identify the external memory and verify connections before attempting a
   direct read. A board-specific SPI wiring tutorial remains to be established.
3. Obtain two independent reads and compare their hashes. Keep the raw files.
4. Decode only with a matching schema and verified geometry:

```powershell
Get-FileHash dumps/external-read1.bin, dumps/external-read2.bin -Algorithm SHA256
python tools/extract_logfs.py dumps/external-read1.bin --out dumps/saved-settings.json
```

For a different confirmed size, specify `--expected-size`, for example with a
hexadecimal value. That switch changes the file-size check; it does not add
support for a different LogFS format or geometry.

The parser uses the first active arena and first valid active record per
object/instance, following the reference lookup behavior. It skips obsolete
records, validates bounds and retains unknown objects as raw data. This format
has no payload CRC: repeat reads and schema validation matter. Missing objects
do not prove the running configuration equals the factory defaults.

Tests cover synthetic LogFS arenas, obsolete records and default payloads.
No external-memory capture from the physical Qimmiq board has been decoded yet.

## Decide whether Rate needs a code change

Inspect `FlightModeSettings`, the stabilization banks, `ManualControlSettings`,
`HwSettings`, `MixerSettings`, `ActuatorSettings` and sensor calibration.
Determine which switch position selects which mode and how roll, pitch and yaw
are stabilized. The existing application implements Rate, so first investigate
a configuration change through the original supported settings mechanism.

Keep an unchanged baseline build and settings backup. If source changes are
eventually needed, start from the matching revision, keep the hardware target
and persisted-object schema stable unless intentionally migrating them, and
review output differences. A change to the schema may invalidate saved objects;
a change to the linker or generated code invalidates old symbol addresses.

No mode modification, hardware write or flight validation is completed at this
checkpoint. Record those results separately when they become available.
