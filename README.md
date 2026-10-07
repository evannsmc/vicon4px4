# Vicon4PX4
### A Vicon → ROS 2 → PX4 External Vision Bridge
![Status](https://img.shields.io/badge/Status-Hardware_Validated-blue)
![Vicon](https://img.shields.io/badge/Vicon-Client_3.7-blue)
[![ROS 2 Humble_Compatible](https://img.shields.io/badge/ROS%202-Humble-blue)](https://docs.ros.org/en/humble/index.html)
[![ROS 2 Jazzy_Compatible](https://img.shields.io/badge/ROS%202-Jazzy-blue)](https://docs.ros.org/en/jazzy/index.html)
[![PX4 Compatible](https://img.shields.io/badge/PX4-Autopilot-pink)](https://github.com/PX4/PX4-Autopilot)
[![evannsmc.com](https://img.shields.io/badge/evannsmc.com-Project%20Page-blue)](https://www.evannsmc.com/projects/mocap4px4)

`vicon4px4` is a ROS 2 (C++) package that streams Vicon motion capture data into the PX4 EKF using External Vision fusion, enabling position and heading fusion for hardware flight experiments. The package converts Vicon ENU measurements to NED, and publishes pose data in quaternions as well as euler angles under the rigid body name as defined in Vicon Tracker.

Another launch file then relays this information for use in PX4 External Vision EKF Fusion by publishing the data as `px4_msgs/msg/VehicleOdometry` messages on `/fmu/in/vehicle_visual_odometry`, and handles the quaternion reordering and timestamping that PX4 expects. A secondary full-state relay node is available to merge the fused EKF output back from `/fmu/out/vehicle_odometry`, and `/fmu/out/vehicle_local_position` into one topic that relays all pose data including available higher order derivatives from the EKF for convenient logging and control.

Derived from [ROS2-Vicon-Receiver](https://github.com/OPT4SMART/ros2-vicon-receiver). Tested with ROS 2 Jazzy Jalisco (Ubuntu 24.04) and Humble Hawksbill (Ubuntu 22.04).

---

## Quick start

Assumes ROS 2 Jazzy or Humble is installed ([guide](https://docs.ros.org/en/jazzy/Installation.html)).

```bash
git clone --recursive https://github.com/evannsmc/vicon4px4.git ~/ws_vicon/src
~/ws_vicon/src/setup.sh
source ~/ws_vicon/install/setup.bash
```

This repository **is** the workspace's `src/` directory: it holds the `vicon4px4` package next to its
dependencies, which are git submodules (`px4_msgs` @ `v1.16_minimal_msgs`, `mocap_msgs`,
`mocap_px4_relays`). `setup.sh` fetches the submodules, installs system dependencies with `rosdep`,
and builds everything with `colcon build --symlink-install` in Release mode.

- **Update:** `git -C ~/ws_vicon/src pull --recurse-submodules && ~/ws_vicon/src/setup.sh`
- **Rebuild without rosdep:** `setup.sh --no-deps` (any other arguments go to `colcon build`)
- **Existing workspace:** clone into `<ws>/src/vicon4px4` instead; `setup.sh` detects this. If that workspace
  already has `px4_msgs`, `mocap_msgs` or `mocap_px4_relays`, remove one copy (or `touch <copy>/COLCON_IGNORE`),
  since colcon refuses duplicate package names.
- **Dev container:** open the repo in VS Code and choose *Reopen in Container* (Jazzy by default;
  set `ROS_DISTRO=humble` on the host for Humble).

### Configure your network

Edit `vicon4px4/config/vicon4px4_params.yaml`:

```yaml
hostname: "192.168.10.2"   # IP of the PC running Vicon Tracker
```

With `--symlink-install` no rebuild is needed. You can also override any parameter at launch
(`hostname:=192.168.10.5`) or pass your own file with `params_file:=/path/to/params.yaml`.
Give this machine a static IP on the same LAN as the Vicon Tracker PC.

### Launch

```bash
# Client + visual odometry relay (typical flight-test configuration)
ros2 launch vicon4px4 bringup.launch.py vo_relay:=true

# ... + full state relay
ros2 launch vicon4px4 bringup.launch.py vo_relay:=true full_state_relay:=true

# Client only
ros2 launch vicon4px4 bringup.launch.py
```

| Argument | Default | Description |
|----------|---------|-------------|
| `vo_relay` | `false` | Run `visual_odometry_relay` (pose -> `/fmu/in/vehicle_visual_odometry`) |
| `full_state_relay` | `false` | Run `full_state_relay` (PX4 EKF -> `mocap_msgs/FullState`) |
| `params_file` | `config/vicon4px4_params.yaml` | Client parameters |
| any [client parameter](#configuration) | from `params_file` | Override a single value |

`ros2 launch vicon4px4 bringup.launch.py --show-args` lists everything. The previous launch files still work
and are shortcuts for the above: `client.launch.py`, `client_and_visual_odometry.launch.py`
(`vo_relay:=true`) and `client_vision_full_all.launch.py` (both relays).

> The relay subscribes to `/vicon/drone/drone`, so name your subject (and segment) `drone` in Vicon Tracker and keep the default `vicon` namespace.

### Example Topic Tree (all three nodes running) assuming your rigid body is named `drone` in the Vicon Tracker app.

```text
/vicon/
├── drone/
│   ├── drone       [geometry_msgs/PoseStamped]
│   └── drone_euler [mocap_msgs/PoseEuler]

/fmu/in/vehicle_visual_odometry          [px4_msgs/VehicleOdometry]   <- to EKF   (mocap_px4_relays)
/merge_odom_localpos/full_state_relay    [mocap_msgs/FullState]       <- from EKF  (mocap_px4_relays)
```

```bash
# Verify vision data is reaching PX4
ros2 topic echo /fmu/in/vehicle_visual_odometry

# Check the merged full-state output
ros2 topic echo /merge_odom_localpos/full_state_relay

# Raw Vicon pose
ros2 topic echo /vicon/drone/drone
```

#### Published topics of the client.launch.py alone

All topics are published under the configured `namespace` (default `vicon`):

```text
/<namespace>/<subject_name>/<segment_name>         [geometry_msgs/PoseStamped]
/<namespace>/<subject_name>/<segment_name>_euler    [mocap_msgs/PoseEuler]
```

- **PoseStamped**: position (x, y, z) + quaternion (qw, qx, qy, qz) in NED
- **PoseEuler**: position (x, y, z) + roll, pitch, yaw in radians

`<subject_name>` and `<segment_name>` are taken verbatim from Vicon Tracker.

#### TF tree

```text
map (world_frame)
└── vicon (vicon_frame)          [static]
    ├── <subject_1>_<segment_1>  [dynamic]
    └── <subject_2>_<segment_2>  [dynamic]
```

The static `map -> vicon` transform is defined by `map_xyz` and `map_rpy`. Dynamic child frames update with each Vicon measurement.

---

## Relay nodes

The **visual_odometry_relay** and **full_state_relay** nodes have been moved to the [`mocap_px4_relays`](mocap_px4_relays/) package so they can be reused with any motion capture source (Vicon, OptiTrack, etc.). See that package's README for full documentation.

### Data pipeline

```text
Vicon Tracker (ENU, millimeters)
        |
   vicon_client node  (vicon4px4)
        |  converts ENU -> NED, mm -> m
        v
  /vicon/*rigid_body_name*/*rigid_body_name* (geometry_msgs/PoseStamped, NED)
        |
  visual_odometry_relay node  (mocap_px4_relays)
        |  reorders quaternion, stamps, publishes at 35 Hz
        v
  /fmu/in/vehicle_visual_odometry  (px4_msgs/VehicleOdometry)
        |
   PX4 EKF2 (fuses vision + IMU)
        |
        v
  /fmu/out/vehicle_odometry & /fmu/out/vehicle_local_position
        |
  full_state_relay node  (mocap_px4_relays)  [optional]
        |  merges both into one topic at 40 Hz
        v
  /merge_odom_localpos/full_state_relay  (mocap_msgs/FullState)
```

For the EKF to accept vision input you must enable it on the PX4 side (the `EKF2_EV_CTRL` and `EKF2_HGT_REF` must be set up according to what your motion capture system can provide). It is also recommended to turn off magnetometer fusion to avoid issues in indoor environments.

---

## Configuration

Parameters of `vicon_client`, read from `vicon4px4/config/vicon4px4_params.yaml` (or `params_file:=`). Each one can be overridden as a launch argument of the same name, except `namespace`, whose launch argument is `topic_namespace`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hostname` | `192.168.10.2` | IP/hostname of the machine running Vicon Tracker |
| `buffer_size` | `200` | Vicon DataStream buffer size |
| `namespace` | `vicon` | Topic namespace prefix |
| `world_frame` | `map` | Global TF reference frame |
| `vicon_frame` | `vicon` | Vicon TF reference frame |
| `map_xyz` | `[0.0, 0.0, 0.0]` | Static translation: world_frame -> vicon_frame (meters) |
| `map_rpy` | `[0.0, 0.0, 0.0]` | Static rotation: world_frame -> vicon_frame |
| `map_rpy_in_degrees` | `false` | If `true`, `map_rpy` values are in degrees |

---

## Requirements

- [Vicon Tracker](https://www.vicon.com/software/tracker/) running on another machine, with DataStream enabled and reachable over the network (hostname/IP)
- ROS 2 Jazzy Jalisco or Humble Hawksbill installed and sourced (at least *ros-jazzy-ros-base* and *ros-dev-tools* packages, [installation guide](https://docs.ros.org/en/jazzy/Installation.html))
- *rosdep* for ROS 2 package dependencies (`setup.sh` initializes it on first run; [guide](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Rosdep.html))
- [`px4_msgs`](https://github.com/evannsmc/px4_msgs/tree/v1.16_minimal_msgs), [`mocap_msgs`](https://github.com/evannsmc/mocap_msgs) and [`mocap_px4_relays`](https://github.com/evannsmc/mocap_px4_relays) are included as git submodules

> Note: you do not need system-wide Boost or the Vicon DataStream SDK; both are vendored per-architecture inside this repository.

---

## Compatibility

- **ROS 2**: Jazzy Jalisco and Humble Hawksbill
- **OS / arch**: Ubuntu 24.04 and 22.04; `x86_64` and `ARM64` tested
- **Vicon stack**: Vicon Tracker; Vicon DataStream SDK **1.12**
- **SDK & Boost**: vendored per-arch inside this repo (no system install needed)

---

## Repository layout

```text
vicon4px4/                          # the repo = your workspace's src/
├── setup.sh                     # submodules + rosdep + colcon build
├── .devcontainer/               # VS Code dev container (Jazzy/Humble)
├── .github/workflows/build.yml  # CI: builds on Humble and Jazzy
├── docs/
├── vicon4px4/                    # the ROS 2 package
│   ├── src/                     # vicon_client node (communicator, publisher, utils)
│   ├── include/vicon4px4/
│   ├── launch/
│   │   ├── bringup.launch.py    # client + optional relays (vo_relay:=, full_state_relay:=)
│   │   └── client*.launch.py    # shortcuts for bringup.launch.py
│   ├── config/vicon4px4_params.yaml
│   ├── third_party/                # vendored Boost 1.75 & Vicon SDK 1.12 (x86_64, aarch64)
├── px4_msgs/                    # submodule (v1.16_minimal_msgs)
├── mocap_msgs/                  # submodule
└── mocap_px4_relays/            # submodule: visual_odometry_relay, full_state_relay
```

---

## Building & linking details

- The package is C++17 and uses `ament_cmake`.
- The **Vicon DataStream SDK (1.12)** and **Boost 1.75** are vendored in `third_party/<arch>/` and linked directly, so you don't need system-wide installations.
- The install step ships the required shared libraries so that runtime lookups succeed without extra `LD_LIBRARY_PATH` setup.

## Troubleshooting / FAQ

**EKF not fusing vision data**: Ensure `EKF2_EV_CTRL` is set to enable position and/or yaw fusion from external vision. Check that `/fmu/in/vehicle_visual_odometry` is being published at the expected rate with `ros2 topic hz`.

**The node can't connect to the Vicon server**: verify `hostname` and network reachability (ping / TCP); check that Vicon Tracker is running and DataStream is enabled.

**Frames look misaligned**: adjust `map_xyz` / `map_rpy` and confirm radians vs degrees via `map_rpy_in_degrees`.

**Full state relay not publishing**: the gating requires both `/fmu/out/vehicle_odometry` and `/fmu/out/vehicle_local_position` to arrive at >= 50 Hz. Confirm PX4 is running and the DDS/uXRCE bridge is healthy.

**I don't see TF in RViz**: confirm TF display is enabled and the fixed frame matches your global frame (`world_frame`/`vicon_frame`).

---


### Frames & mapping

- The Vicon frame -> world frame mapping is configurable via `world_frame`, `vicon_frame`, `map_xyz` and `map_rpy`.
- `map_rpy_in_degrees` lets you specify rotations in degrees when convenient.
- Frame IDs for subjects/segments are derived from Vicon names.

> Units follow ROS conventions (positions in meters, rotations in radians) in downstream consumers; ensure your system uses consistent units end-to-end.

---

## Example images

### TF2 frame tree

<img src="docs/images/tf_tree.png" alt="TF2 frame tree for vicon4px4" width="720">

Example TF tree showing the static `world_frame -> vicon_frame` transform and dynamic subject frames.

### RViz: TF and Pose

<img src="docs/images/rviz_tf_pose.png" alt="RViz visualization of TF and PoseStamped" width="720">

RViz view showing TF frames and a Pose display for a tracked subject.

---


## Website

This project is part of the [evannsmc open-source portfolio](https://www.evannsmc.com/projects).

- [Project page](https://www.evannsmc.com/projects/mocap4px4)

## License & attribution

- **License:** GNU General Public License v3.0 (GPL-3.0)
