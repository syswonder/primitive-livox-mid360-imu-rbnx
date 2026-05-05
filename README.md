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

## Boot ordering

`mid360_lidar_rbnx` MUST initialize first. Until its
`Driver(CMD_INIT)` succeeds, the upstream livox launch isn't running
and `/livox/imu` doesn't exist on the bus — our sentinel will time
out. The deploy manifest should list mid360_lidar_rbnx ahead of
mid360_imu_rbnx.

## Config (passed via `Driver(CMD_INIT, config_json)`)

```json
{
  "imu_topic":          "/livox/imu",
  "sentinel_timeout_s": 30.0
}
```

## License

MulanPSL-2.0.
