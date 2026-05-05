#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Start the atlas bridge. No ROS spawn — this package only listens on
# /livox/imu (already published by mid360_lidar_rbnx's livox launch).
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

ROS_DISTRO="${ROS_DISTRO:-humble}"
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"

export PYTHONPATH="$PKG/rbnx-build/codegen/proto_gen:${PYTHONPATH:-}"
if ROBONIX_PY="$(rbnx path robonix-py 2>/dev/null)"; then
    export PYTHONPATH="$ROBONIX_PY:$PYTHONPATH"
fi

exec python3 -m mid360_imu.atlas_bridge
