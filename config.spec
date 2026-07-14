# Runtime config accepted by the MID-360 IMU primitive.
#
# The lidar process owns the physical device and publishes this stream; this
# package declares and validates the IMU capability. This file documents the
# package `config:` mapping and is not loaded by the provider.

config:
  # string, default: /livox/imu.
  # Absolute ROS topic produced by the MID-360 driver and monitored for an IMU
  # sample before this provider becomes ACTIVE.
  imu_topic: /livox/imu

  # float (seconds), default: 30.0.
  # Maximum startup wait for the first sensor_msgs/Imu message.
  sentinel_timeout_s: 30.0
