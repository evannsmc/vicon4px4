"""Bring up the Vicon client and, optionally, the PX4 relays.

Defaults come from config/vicon4px4_params.yaml (or `params_file:=...`).
Any client parameter can be overridden on the command line; arguments left
empty fall back to the params file.

    ros2 launch vicon4px4 bringup.launch.py                        # client only
    ros2 launch vicon4px4 bringup.launch.py vo_relay:=true         # + vision -> PX4
    ros2 launch vicon4px4 bringup.launch.py vo_relay:=true full_state_relay:=true
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PACKAGE = 'vicon4px4'
NODE_NAME = 'vicon_client'

# launch argument -> (node parameter, type, description)
CLIENT_ARGS = {
    'hostname': ('hostname', str, 'Vicon server hostname or IP address'),
    'buffer_size': ('buffer_size', int, 'Buffer size for Vicon data'),
    'topic_namespace': ('namespace', str, 'Topic namespace for Vicon messages'),
    'world_frame': ('world_frame', str, 'World frame for tf2 transformations'),
    'vicon_frame': ('vicon_frame', str, 'Vicon frame for tf2 transformations'),
    'map_xyz': ('map_xyz', list, 'XYZ translation world_frame -> vicon_frame'),
    'map_rpy': ('map_rpy', list, 'RPY rotation world_frame -> vicon_frame'),
    'map_rpy_in_degrees': ('map_rpy_in_degrees', bool, 'Whether map_rpy is in degrees'),
}


def _parse(value, kind):
    if kind is str:
        return value
    parsed = yaml.safe_load(value)
    if kind is list:
        return [float(v) for v in parsed]
    return kind(parsed)


def _launch_setup(context):
    params_file = LaunchConfiguration('params_file').perform(context)

    overrides = {}
    for arg, (param, kind, _) in CLIENT_ARGS.items():
        value = LaunchConfiguration(arg).perform(context)
        if value != '':
            overrides[param] = _parse(value, kind)

    return [
        Node(
            package=PACKAGE,
            executable=NODE_NAME,
            output='screen',
            parameters=[params_file, overrides],
        ),
        # Subscribes to /vicon/drone/drone (hardcoded in mocap_px4_relays).
        Node(
            package='mocap_px4_relays',
            executable='visual_odometry_relay',
            output='screen',
            condition=IfCondition(LaunchConfiguration('vo_relay')),
        ),
        Node(
            package='mocap_px4_relays',
            executable='full_state_relay',
            output='screen',
            condition=IfCondition(LaunchConfiguration('full_state_relay')),
        ),
    ]


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory(PACKAGE), 'config', f'{PACKAGE}_params.yaml')

    args = [
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='YAML file with vicon_client parameters'),
        DeclareLaunchArgument('vo_relay', default_value='false',
                              description='Also run visual_odometry_relay (pose -> PX4 EKF)'),
        DeclareLaunchArgument('full_state_relay', default_value='false',
                              description='Also run full_state_relay (PX4 EKF -> FullState)'),
    ]
    args += [
        DeclareLaunchArgument(arg, default_value='',
                              description=f'{desc} (empty: use params_file)')
        for arg, (_, _, desc) in CLIENT_ARGS.items()
    ]

    return LaunchDescription(args + [OpaqueFunction(function=_launch_setup)])
