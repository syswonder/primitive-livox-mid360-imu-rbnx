#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Spawn the mid360_imu capability process. No ROS subprocess — the IMU
# topic comes from mid360_lidar_rbnx's livox launch as a side-effect.
set -euo pipefail
: "${AMENT_TRACE_SETUP_FILES:=}"
: "${COLCON_TRACE:=}"
export AMENT_TRACE_SETUP_FILES COLCON_TRACE
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

ROS_DISTRO="${ROS_DISTRO:-humble}"
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"

if ROBONIX_API="$(rbnx path robonix-api 2>/dev/null)"; then
    export PYTHONPATH="$ROBONIX_API:$PKG:${PYTHONPATH:-}"
fi

exec python3 -m mid360_imu.main
