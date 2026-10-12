# Qimmiq Racer firmware research

Reproduce and understand the firmware from a Qimmiq Racer flight controller, then investigate how to enable FPV/Acro control. This repository contains an original internal-flash dump, analysis tools and a verified OpenPilot build reference.

**Current milestone: the original application has been recompiled byte for byte.** A complete matching flash image can also be reconstructed by retaining the original bootloader and board information. The drone's saved settings have **not** been recovered, and no modified firmware has been flashed or flight-tested.

Another Qimmiq Racer may have a different board revision or firmware. Compare your own backup before applying this reference to your hardware.

## What has been verified

| Item | Result |
|---|---|
| Reported MCU marking | STM32F103CBT6, 128 KiB flash / 20 KiB SRAM |
| Original dump | [`firmware.bin`](firmware.bin), 131072 bytes starting at `0x08000000` |
| Application | OpenPilot `RELEASE-15.02.01`, target `coptercontrol`, CC3D board type/revision `04/02` |
| Exact source revision | [`bf68cc84d471feb0d9346f40f012e6c8e4de4bbb`](https://github.com/librepilot/LibrePilot/tree/bf68cc84d471feb0d9346f40f012e6c8e4de4bbb), retained in LibrePilot history |
| Application comparison | 95896 bytes, **zero differences** |
| Software stack | STM32F1 Standard Peripheral Library, PIOS, FreeRTOS V8.0.1 |
| UAVObjects | 104 definitions, including 35 settings objects |
| Symbol recovery | 1457 symbols; 1070 functions with sizes in the verified export |
| Full upstream build | Differs from the dump; its bootloader must not replace the original as an assumed equivalent |
| Saved settings / physical wiring | Still to recover or verify on the board |

Reference dump SHA-256:

```text
ec90df9a62bfb389fe555c82dd5192eda0db17ec880896aa340456b8e15de3fc
```

See the machine-readable [application comparison](analysis/baseline/comparison.json), [full-image reconstruction report](analysis/baseline/firmware-1for1.json) and [source provenance](analysis/baseline/provenance.json).

The [checkpoint record](docs/checkpoint.md) lists completed work and remaining validation.

## 1. Start with the reference dump

You can run the analysis without connecting a drone. Install Git and Python 3, then run these commands in PowerShell:

```powershell
git clone https://github.com/guedesite/qimmiq-racer-drone-firmware.git
cd qimmiq-racer-drone-firmware
Get-FileHash firmware.bin -Algorithm SHA256
python tools/inspect_dump.py firmware.bin
python -m unittest discover -s tests -v
```

The inventory is written to `analysis/raw_inventory.json`. It identifies vector tables, printable strings, erased regions and OpenPilot descriptors. All nine tests can run from a fresh clone using the checked-in schema. After downloading and building the upstream source, the schema test also checks regenerated layouts and generated object IDs.

The checked-in reports describe the reference dump above. Running a tool on a different dump does not make those reports evidence for your board; use separate output files.

## 2. Back up your own board

Remove the propellers before connecting or testing the flight controller. Keep the original firmware and settings backups separate from any experiments.

If you already have a raw internal-flash dump, place it in `dumps/`, which Git ignores. Otherwise, obtain a read-only backup using a compatible SWD programmer and the board's **verified** SWD connections. The internal-flash range for this MCU is `0x08000000` through `0x0801FFFF`, or 128 KiB. This repository does not yet provide a verified Qimmiq Racer pad pinout. Do not guess solder pads or supply voltages. Do not clear readout protection to obtain a backup: that can erase flash.

Read the flash twice and compare the files:

```powershell
New-Item -ItemType Directory -Force dumps | Out-Null
Get-FileHash dumps/my-racer-read1.bin, dumps/my-racer-read2.bin -Algorithm SHA256
python tools/inspect_dump.py dumps/my-racer-read1.bin --out dumps/my-racer-inventory.json
```

Matching the reference SHA-256 establishes identical internal-flash contents. It does not establish identical calibration, radio configuration or external-flash settings. If your hash differs, investigate the descriptors and application first; do not assume the symbol addresses or reconstructed image apply.

If an already working, compatible OpenPilot GCS connection is available, export the settings before changing modes or running setup wizards. Also preserve external flash and record option bytes where your readout tools support this. No verified external-memory capture procedure or restore procedure for this particular board is included yet.

## 3. Download the exact source and tools

The reproducible build uses WSL with Ubuntu, Python 3 on Windows, GNU ARM Embedded `4.9-2014-q4-major`, and a locally built Python 2.7.18 for the historical build scripts. Python 2 is confined to the build environment. Downloads require internet access and several hundred megabytes of storage.

Install WSL/Ubuntu if needed, then install the build dependencies inside Ubuntu:

```powershell
wsl -d Ubuntu -- sudo apt-get update
wsl -d Ubuntu -- sudo apt-get install -y --no-install-recommends build-essential qtbase5-dev qt5-qmake libc6-i386 lib32stdc++6 lib32z1 ca-certificates pkg-config
python tools/prepare_baseline.py
python tools/fetch_baseline_toolchains.py
```

If your distribution has another name, substitute it for `Ubuntu` (`wsl --list --quiet` lists installed distributions). The downloads are pinned; provenance and toolchain hashes are recorded under `analysis/baseline/`. The large source tree, archives and toolchains are ignored by Git. Do not rerun source extraction while a build is running.

## 4. Recompile and verify the application

Run from the repository root in PowerShell:

```powershell
wsl -d Ubuntu -- bash tools/build_baseline.sh
$sourceRoot = 'analysis/baseline/LibrePilot-bf68cc84d471feb0d9346f40f012e6c8e4de4bbb'
$buildRoot = "$sourceRoot/build/fw_coptercontrol"
python tools/compare_baseline.py firmware.bin "$buildRoot/fw_coptercontrol.bin"
python tools/uavo_schema.py "$sourceRoot/shared/uavobjectdefinition"
python tools/export_baseline_symbols.py firmware.bin "$buildRoot/fw_coptercontrol.bin" analysis/baseline/application-symbols.txt
python -m unittest discover -s tests -v
```

The expected comparison is `identical: true`, with 95896 compiled application bytes and zero differences. The expected UAVO SHA-1 is `e700bb5174d04ca794312e6234a78b01469143df`. Stop and investigate any mismatch before treating build symbols as addresses in the original firmware.

The build log is `analysis/baseline/firmware-build.log`. These commands compile and compare files; they do not program connected hardware.

## 5. Reconstruct the original full image

The application binary alone is not a complete flash backup. To regenerate a full image, including matching descriptors, first build the upstream packaged image:

```powershell
wsl -d Ubuntu -- bash tools/build_baseline.sh --full
$sourceRoot = 'analysis/baseline/LibrePilot-bf68cc84d471feb0d9346f40f012e6c8e4de4bbb'
$buildRoot = "$sourceRoot/build/fw_coptercontrol"
```

Follow the [full-image reconstruction instructions](docs/reproduction-and-settings.md#reconstruct-the-full-image). The reconstruction script accepts the **100-byte descriptor**, not the complete `.opfw` package, and refuses to produce an image differing from the original dump.

The resulting `analysis/baseline/firmware-1for1.bin` must have the reference SHA-256. Its application and descriptors are rebuilt; the first 12 KiB of bootloader and board information are copied from the original dump. **This is a verification artifact, not a tested flashing or recovery procedure.**

## 6. Recover the settings before changing flight modes

The exact build proves the compiled code and defaults match. It does not recover the settings saved on your drone. The CC3D reference stores persistent UAVObjects in external SPI flash. Confirm the installed device, JEDEC identification and memory geometry before decoding a physical dump.

Once a verified full 2 MiB external dump is available for the reference geometry:

```powershell
python tools/extract_logfs.py dumps/external-flash.bin --out dumps/saved-settings.json
```

The decoder reports active LogFS records, known fields and differences from factory payloads. Missing records do not prove that the running drone uses defaults. This tool has been tested against synthetic LogFS data; it has not yet been validated against this drone's external memory.

## 7. Investigate FPV / Acro

OpenPilot already implements **Rate** stabilization. In Rate mode, sticks command angular velocity; centered roll/pitch sticks request zero angular velocity, without auto-leveling. This is not an absolute angle lock. Keep throttle handling as a separate decision; selecting `Manual` for every stabilization axis is not equivalent to Acro.

The next step is to recover `FlightModeSettings`, stabilization settings, receiver mappings and actuator/mixer settings, then determine what the current “rolling/gambling” switch actually selects. The product's mode name alone does not identify the algorithm. A settings change may be sufficient; a firmware patch is not yet justified by the evidence.

For deeper analysis, use the [Ghidra and control-loop guide](docs/firmware-analysis.md). The verified symbol export allows source-level navigation of the original application. Ghidra scripts are provided, but have not yet been executed in Ghidra on this project.

## Repository layout

```text
firmware.bin                    Original reference internal-flash dump
docs/                           Analysis, reproduction and settings guides
tools/                          Python analysis tools and WSL build wrapper
tools/ghidra/                   Ghidra preparation, inventory and symbol import
tests/                          Offline regression tests
analysis/raw_inventory.json     Reference dump inventory
analysis/baseline/              Checked-in evidence, schema and verified symbols
dumps/                          Your private backups (ignored by Git)
```

Generated build binaries, source downloads, logs and Ghidra projects stay local. The original dump and compact evidence are versioned so another owner can verify the same starting point.

## Contributing

Include the board revision, MCU marking, internal dump hash, tool versions and reproducible steps with new findings. Clearly distinguish physical measurements, byte-verified results and hypotheses. Do not upload someone else's receiver configuration or calibration without their agreement. Hardware modification, flashing and flight-test results should state exactly which board and image were tested.

Upstream OpenPilot/LibrePilot sources retain their original license notices; their license files are available in the pinned source tree. This repository does not claim authorship of the original firmware. See [NOTICE.md](NOTICE.md) for attribution and scope.
