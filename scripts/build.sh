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

FLAGS=(--ros2 --out-dir "$PKG/rbnx-build/codegen")
[[ "$CLEAN" == "1" ]] && FLAGS+=(--clean)
echo "[mid360_imu/build] rbnx codegen ${FLAGS[*]}"
rbnx codegen -p "$PKG" "${FLAGS[@]}"

ROS_DISTRO="${ROS_DISTRO:-humble}"
set +u; source "/opt/ros/${ROS_DISTRO}/setup.bash"; set -u
ROS2_IDL="$PKG/rbnx-build/codegen/ros2_idl"
echo "[mid360_imu/build] colcon build (Robonix ROS 2 interfaces)"
(cd "$ROS2_IDL" && colcon build)

touch "$PKG/rbnx-build/.rbnx-built"
echo "[mid360_imu/build] done."
