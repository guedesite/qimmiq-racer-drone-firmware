#!/usr/bin/env bash
# Run under WSL Ubuntu. Builds a reference; never programs connected hardware.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline="$repo_root/analysis/baseline"
source_root="$baseline/LibrePilot-bf68cc84d471feb0d9346f40f012e6c8e4de4bbb"
runtime_root="/tmp/qimmiq-openpilot-bf68cc84-toolchains"
mkdir -p "$runtime_root"
target=fw_coptercontrol
build_log="$baseline/firmware-build.log"
if [[ "${1:-}" == --objects-only ]]; then
    target=uavobjects_flight
    build_log="$baseline/uavo-build.log"
    shift
elif [[ "${1:-}" == --full ]]; then
    target=ef_coptercontrol
    build_log="$baseline/full-flash-build.log"
    shift
fi

if [[ ! -x "$runtime_root/python2/bin/python2.7" ]]; then
    tar -xzf "$baseline/toolchains/Python-2.7.18.tgz" -C "$runtime_root"
    (
        cd "$runtime_root/Python-2.7.18"
        ./configure --prefix="$runtime_root/python2" --without-ensurepip > "$baseline/python2-configure.log" 2>&1
        make -j8 > "$baseline/python2-build.log" 2>&1
        make install > "$baseline/python2-install.log" 2>&1
    )
fi
if [[ "$target" != uavobjects_flight && ! -x "$runtime_root/gcc-arm-none-eabi-4_9-2014q4/bin/arm-none-eabi-gcc" ]]; then
    tar -xjf "$baseline/toolchains/gcc-arm-none-eabi-4_9-2014q4-20141203-linux.tar.bz2" -C "$runtime_root"
fi
export PATH="$runtime_root/python2/bin:$runtime_root/gcc-arm-none-eabi-4_9-2014q4/bin:$PATH"
python2.7 --version
if [[ "$target" != uavobjects_flight ]]; then arm-none-eabi-gcc --version; fi
qmake --version
cd "$source_root"
make -j8 "$target" PYTHON="$runtime_root/python2/bin/python2.7" QMAKE=qmake "$@" > "$build_log" 2>&1
if [[ "$target" != uavobjects_flight ]]; then
    arm-none-eabi-nm -n -S --defined-only build/fw_coptercontrol/fw_coptercontrol.elf > "$baseline/application-symbols.txt"
fi
printf 'Completed %s, log: %s\n' "$target" "$build_log"
