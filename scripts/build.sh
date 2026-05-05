#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Build phase: rbnx codegen only. This package doesn't vendor any
# ROS source — it's a pure topic shim that subscribes to /livox/imu
# (made live by mid360_lidar_rbnx) and atlas-registers it.
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"
CLEAN="${RBNX_BUILD_CLEAN:-}"

if [[ "$CLEAN" == "1" ]]; then
    echo "[mid360_imu/build] clean: removing rbnx-build/"
    rm -rf rbnx-build
fi
mkdir -p rbnx-build/data

FLAGS=(--out-dir "$PKG/rbnx-build/codegen")
[[ "$CLEAN" == "1" ]] && FLAGS+=(--clean)
echo "[mid360_imu/build] rbnx codegen ${FLAGS[*]}"
rbnx codegen -p "$PKG" "${FLAGS[@]}"

touch "$PKG/rbnx-build/.rbnx-built"
echo "[mid360_imu/build] done."
