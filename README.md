# mid360_imu_rbnx

Robonix package owning the `primitive/imu/*` namespace for the Ranger
Mini's MID-360 embedded IMU. The IMU stream itself is produced by the
upstream `livox_ros_driver2` launch (spawned by `mid360_lidar_rbnx`)
and published on `/livox/imu`. **This package does NOT spawn any ROS
process** — it's a pure topic shim that atlas-registers the existing
topic.

The split exists because robonix's invariant is "one primitive
namespace = one package". Mixing `primitive/lidar/*` and
`primitive/imu/*` in the same package would let two namespaces share
one capability_id, breaking that rule.

## Capability surface

| Contract                       | Mode      | Transport | Source / handler                            |
| ------------------------------ | --------- | --------- | ------------------------------------------- |
| `robonix/primitive/imu/driver` | rpc       | gRPC      | `Driver(CMD_INIT, config_json)` — lifecycle |
| `robonix/primitive/imu/imu`    | topic_out | ROS 2     | `/livox/imu` (sensor_msgs/Imu)              |

## Driver-init lifecycle

`start.sh` brings up the atlas bridge. The bridge:

1. opens a gRPC server (default port 50233),
2. registers the capability and declares **only**
   `primitive/imu/driver` on atlas,
3. blocks awaiting `Driver(CMD_INIT, config_json)`.

When `rbnx boot` calls Init, the handler subscribes to the configured
IMU topic and waits for the first `sensor_msgs/Imu` message — that's
the sentinel proving the upstream livox driver is alive on this host's
DDS bus. Once it arrives, we declare `primitive/imu/imu` on atlas and
return ok.

## Boot ordering — defer, no dep graph

Robonix doesn't track package startup dependencies. The deploy manifest
is an unordered list. Instead, packages defer themselves at runtime:

If `mid360_lidar_rbnx`'s Init hasn't completed yet, `/livox/imu` is
silent. Our Init does a short probe (default 2 s) and returns
`Driver_Response(ok=False, state="deferred")`. `rbnx boot` collects
deferred drivers and retries them periodically until the system reaches
steady state (all ready, or no progress in a round → reported as stuck).

This is intentionally simpler than a topological dep graph: each
package only declares what it needs at the moment its Init runs, so
there's no manifest-drift problem when contracts change shape.

## Config (passed via `Driver(CMD_INIT, config_json)`)

```json
{
  "imu_topic":          "/livox/imu",
  "sentinel_timeout_s": 30.0
}
```

## License

MulanPSL-2.0.
