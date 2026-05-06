#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
"""mid360_imu_rbnx — atlas bridge.

Owns the `primitive/imu/*` namespace for the Ranger Mini's MID-360 IMU.
The IMU is published as a side-effect of `mid360_lidar_rbnx`'s upstream
`livox_ros_driver2` launch on `/livox/imu`; this package does NOT spawn
any ROS process — it just atlas-registers the existing topic.

Boot order: `mid360_lidar_rbnx` must initialize first; otherwise
`/livox/imu` won't be live and our Init sentinel will time out.

Lifecycle:
  1. start.sh launches THIS process.
  2. main() opens a gRPC server, RegisterCapability, declares ONLY
     `primitive/imu/driver` on atlas, blocks on heartbeat.
  3. `rbnx boot` calls `Driver(CMD_INIT, config_json)`.
  4. The Init handler waits for the first sensor_msgs/Imu on the
     configured topic, then declares `primitive/imu/imu`.

Config (passed via `Driver(CMD_INIT, config_json)`):
    imu_topic          default "/livox/imu"
    sentinel_timeout_s default 30.0
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent import futures
from pathlib import Path

logging.basicConfig(level=os.environ.get("MID360_IMU_LOG_LEVEL", "INFO"),
                    format="[mid360_imu] %(message)s")
log = logging.getLogger("mid360_imu")


def _ensure_proto_gen() -> None:
    d = Path(__file__).resolve().parent
    while d.parent != d:
        pg = d / "rbnx-build" / "codegen" / "proto_gen"
        if pg.is_dir() and (pg / "atlas_pb2.py").exists():
            sys.path.insert(0, str(pg))
            return
        d = d.parent


_ensure_proto_gen()

import grpc  # noqa: E402
import atlas_pb2 as pb  # noqa: E402
import atlas_pb2_grpc as pb_grpc  # noqa: E402
import lifecycle_pb2  # noqa: E402
import robonix_contracts_pb2_grpc as contracts_grpc  # noqa: E402

CMD_INIT = 0
CMD_SHUTDOWN = 1


_state_lock = threading.Lock()
_atlas_stub: pb_grpc.AtlasStub | None = None
_cap_id: str = ""
_initialized = False


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


def _decl_topic_out(contract_id: str, topic: str, qos_profile: str = "best_effort") -> None:
    if _atlas_stub is None:
        return
    _atlas_stub.DeclareInterface(pb.DeclareInterfaceRequest(
        capability_id=_cap_id,
        contract_id=contract_id,
        transport=pb.TRANSPORT_ROS2,
        endpoint=topic,
        params=pb.TransportParams(ros2=pb.Ros2Params(qos_profile=qos_profile)),
    ))


class _ImuDriverServicer(contracts_grpc.PrimitiveImuDriverServicer):
    def Driver(self, request, context):
        cmd = int(request.command)
        if cmd == CMD_INIT:
            try:
                cfg = json.loads(request.config_json) if request.config_json else {}
            except json.JSONDecodeError as e:
                return lifecycle_pb2.Driver_Response(
                    ok=False, state="error", error=f"bad config_json: {e}"
                )
            return self._init(cfg)
        if cmd == CMD_SHUTDOWN:
            return lifecycle_pb2.Driver_Response(ok=True, state="shutdown", error="")
        return lifecycle_pb2.Driver_Response(
            ok=False, state="error", error=f"invalid command {cmd}"
        )

    def _init(self, cfg: dict):
        global _initialized
        with _state_lock:
            if _initialized:
                return lifecycle_pb2.Driver_Response(ok=True, state="ready", error="")

        imu_topic = cfg.get("imu_topic", "/livox/imu")
        # Short probe — we're a topic shim with NO underlying ROS process
        # to spawn, so if the topic isn't there yet it's because our peer
        # (mid360_lidar_rbnx) hasn't completed Init. Return `deferred`
        # fast and let rbnx boot retry us once it has — far cheaper than
        # holding the full sentinel_timeout for a known-async wait.
        defer_probe = float(cfg.get("defer_probe_s", 2.0))

        if not _wait_for_imu(imu_topic, defer_probe):
            return lifecycle_pb2.Driver_Response(
                ok=False, state="deferred",
                error=f"waiting for {imu_topic} (mid360_lidar_rbnx not initialized yet?)",
            )

        try:
            _decl_topic_out("robonix/primitive/imu/imu", imu_topic)
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.ALREADY_EXISTS:
                return lifecycle_pb2.Driver_Response(
                    ok=False, state="error", error=f"declare failed: {e.details()}"
                )

        with _state_lock:
            _initialized = True
        log.info("init complete: imu=%s", imu_topic)
        return lifecycle_pb2.Driver_Response(ok=True, state="ready", error="")


def _start_driver_grpc(port: int) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    contracts_grpc.add_PrimitiveImuDriverServicer_to_server(
        _ImuDriverServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log.info("LifecycleDriver gRPC serving on 0.0.0.0:%d", port)


def _decl_driver_iface(port: int) -> None:
    if _atlas_stub is None:
        return
    _atlas_stub.DeclareInterface(pb.DeclareInterfaceRequest(
        capability_id=_cap_id,
        contract_id="robonix/primitive/imu/driver",
        transport=pb.TRANSPORT_GRPC,
        endpoint=f"127.0.0.1:{port}",
        params=pb.TransportParams(grpc=pb.GrpcParams(
            proto_file="robonix_contracts.proto",
            service_name="PrimitiveImuDriver",
            method="Driver",
        )),
    ))


def _heartbeat_loop() -> None:
    while True:
        time.sleep(15.0)
        if _atlas_stub is None:
            continue
        try:
            _atlas_stub.Heartbeat(pb.HeartbeatRequest(capability_id=_cap_id))
        except Exception as e:  # noqa: BLE001
            log.debug("heartbeat: %s", e)


def _on_signal(signum, _frame):
    log.info("signal %d — shutting down", signum)
    sys.exit(0)


def main() -> None:
    global _atlas_stub, _cap_id
    atlas_addr = os.environ.get("ROBONIX_ATLAS", "127.0.0.1:50051")
    driver_port = int(os.environ.get("MID360_IMU_DRIVER_PORT", "50233"))
    _cap_id = os.environ.get(
        "ROBONIX_CAPABILITY_ID", "com.robonix.ranger.mid360_imu"
    )

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    _start_driver_grpc(driver_port)

    channel = grpc.insecure_channel(atlas_addr)
    _atlas_stub = pb_grpc.AtlasStub(channel)
    pkg_dir = os.environ.get("ROBONIX_PKG_HOST_DIR", "")
    md_path = f"{pkg_dir}/CAPABILITY.md" if pkg_dir else ""
    try:
        _atlas_stub.RegisterCapability(pb.RegisterCapabilityRequest(
            capability_id=_cap_id,
            namespace="robonix/primitive/imu",
            capability_md_path=md_path,
        ))
        _decl_driver_iface(driver_port)
        log.info("registered cap %s, driver iface on :%d (awaiting INIT)",
                 _cap_id, driver_port)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
            log.info("cap %s already registered (re-deploy); ok", _cap_id)
        else:
            log.warning("atlas registration failed: %s", e)

    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    log.info("ready — awaiting Driver(CMD_INIT)")
    try:
        while True:
            time.sleep(60.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
