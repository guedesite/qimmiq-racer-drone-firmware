# Reference evidence

Reports in this directory describe the checked-in `../firmware.bin`, not every
Qimmiq Racer. The [main README](../README.md) gives its hash and scope.

| File | Purpose |
|---|---|
| `raw_inventory.json` | Vectors, strings, descriptors and erased-region inventory |
| `baseline/provenance.json` | Pinned source archive and expected application/UAVO hashes |
| `baseline/toolchain_downloads.json` | Downloaded compiler and Python archive hashes |
| `baseline/comparison.json` | Direct byte comparison of original and rebuilt application |
| `baseline/firmware-1for1.json` | Exact reconstruction and upstream full-image differences |
| `baseline/uavo_schema.json` | Object layouts, IDs and factory payloads; not recovered settings |
| `baseline/application-symbols.txt` | Symbol listing from the verified rebuilt ELF |
| `baseline/verified_symbols.json` | Hash-guarded labels for the matching application |
| `baseline/artifacts/manifest.json` | Hashes of locally saved build artifacts |

Large downloads, source snapshots, build outputs, reconstructed image, logs
and Ghidra projects are ignored by Git. Regenerate them using the tutorial.
Keep per-board captures and decoded private settings under ignored `dumps/`.

ELF and map-file hashes in the artifact manifest describe the saved local build;
debug paths can differ between build directories. Use direct application-byte
comparison to establish firmware equality on another machine.
