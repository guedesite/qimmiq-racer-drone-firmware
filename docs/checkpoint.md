# Checkpoint: byte-identical OpenPilot application

Date: 2026-10-12.

## Completed

- Preserved and fingerprinted the original 128 KiB internal-flash dump.
- Identified the exact OpenPilot revision and CC3D application target.
- Built the historical application and compared every byte: 95896 bytes match.
- Reproduced the OpFw descriptors and UAVObject definition hash.
- Reconstructed the complete original image while explicitly preserving its
  bootloader and board information.
- Exported verified application symbols and the 104-object schema.
- Implemented guarded file patching and an external LogFS decoder.
- Passed nine offline regression tests, including synthetic LogFS cases.

## Not yet established

- Physical board pinout, installed external-memory identity and sensor wiring.
- Saved receiver, calibration, mixer, PID and flight-mode configuration.
- Ghidra script execution against the project.
- Exact-source reproduction of the vendor bootloader.
- A tested restore or experimental flashing procedure for this board.
- Any hardware or flight validation of a modified mode.

## Next milestone

Recover and verify the saved settings, identify the switch mapping, and determine
whether the existing Rate mode can be selected without modifying application
code. Document the hardware capture process so another owner can reproduce it.

The local Git checkpoint is tagged `checkpoint/openpilot-15.02.01-identical`.
Publishing the repository or tag is a separate operation.
