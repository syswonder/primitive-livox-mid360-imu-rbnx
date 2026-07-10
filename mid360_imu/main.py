#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
"""mid360_imu_rbnx — MID-360 IMU primitive (capability_id=mid360_imu).

Topic shim: the MID-360's livox_ros_driver2 launch (owned by
`mid360_lidar_rbnx`) publishes /livox/imu as a side-effect; this
package owns `robonix/primitive/imu/*` and exposes that topic via atlas
without spawning any extra ROS process.

Boot order: mid360_lidar must finish on_init before this cap's on_init
runs (otherwise /livox/imu won't exist yet). The ranger deploy manifest
already orders mid360_lidar before mid360_imu in the `primitive:` list.

Config (from manifest's `config:` block, delivered via Driver(CMD_INIT)):
    imu_topic          default "/livox/imu"
    sentinel_timeout_s default 30.0
"""
from __future__ import annotations

import logging
import os
import threading
import time

from robonix_api import Deferred, Err, Ok, Primitive

logging.basicConfig(
    level=os.environ.get("MID360_IMU_LOG_LEVEL", "INFO"),
    format="[mid360_imu] %(message)s",
)
log = logging.getLogger("mid360_imu")

cap = Primitive(id="mid360_imu", namespace="robonix/primitive/imu")


def _wait_for_imu(topic: str, timeout_s: float) -> bool:
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
        from sensor_msgs.msg import Imu
    except ImportError as e:
        log.warning("rclpy unavailable (%s); skipping sentinel wait", e)
        return True
    rclpy.init(args=None)
    node = Node("mid360_imu_atlas_sentinel")
    qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )
    seen = threading.Event()
    node.create_subscription(Imu, topic, lambda _m: seen.set(), qos)
    log.info("waiting for first IMU sample on %s — up to %.1fs", topic, timeout_s)
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
            if seen.is_set():
                break
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:  # noqa: BLE001
            pass
    return seen.is_set()


@cap.on_init
def init(cfg: dict):
    """REGISTERED → INACTIVE: subscribe to /livox/imu, declare topic_out."""
    imu_topic = cfg.get("imu_topic", "/livox/imu")
    sentinel_timeout = float(cfg.get("sentinel_timeout_s", 30.0))

    if not _wait_for_imu(imu_topic, sentinel_timeout):
        return Deferred(
            f"no IMU on {imu_topic} within {sentinel_timeout:.1f}s "
            "(mid360_lidar may not have finished init yet)"
        )

    cap.declare_ros2_topic(
        "robonix/primitive/imu/imu",
        topic=imu_topic,
        qos="best_effort",
    )
    log.info("init complete: imu=%s", imu_topic)
    return Ok()


if __name__ == "__main__":
    cap.run()
