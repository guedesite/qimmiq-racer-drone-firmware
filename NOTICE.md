# Attribution and scope

The reference application matches OpenPilot `RELEASE-15.02.01`, revision
`bf68cc84d471feb0d9346f40f012e6c8e4de4bbb`, available in the
[LibrePilot repository](https://github.com/librepilot/LibrePilot/tree/bf68cc84d471feb0d9346f40f012e6c8e4de4bbb).
Credit belongs to the upstream OpenPilot, LibrePilot, PIOS, FreeRTOS and
STM32 library contributors according to their respective notices.

`prepare_baseline.py` downloads the original tree, including `LICENSE.txt`,
`GPLv3.txt` and component license notices. Preserve those notices when working
with or distributing upstream sources and derived builds.

`firmware.bin` is the original extracted reference image. Only its application
and OpenPilot descriptors have been reproduced from the pinned source. The
bootloader and board-information region are preserved from the dump; their
exact source provenance has not been established.

Analysis reports and scripts document this research. No additional blanket
license is asserted here for the vendor image or third-party components.
