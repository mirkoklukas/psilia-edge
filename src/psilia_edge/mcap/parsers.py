from __future__ import annotations

from typing import Callable

import numpy as np
from mcap_ros2.reader import McapROS2Message


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Parser registry
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_parser_registry: dict[str, Callable[..., dict | list[dict]]] = {}


def register_parser(schema_name: str):
    def decorator(fn):
        _parser_registry[schema_name] = fn
        return fn

    return decorator


def base_message_parser(msg: McapROS2Message, *, include_ros_msg: bool = False) -> dict:
    result = {
        **_parse_timestamps(msg),
        "__schema_name__": msg.schema.name,
        "__topic__": msg.channel.topic,
    }
    if include_ros_msg:
        result["__ros_msg__"] = msg.ros_msg

    return result


# TODO: Not sure I like returning dict OR list[dict]
#   Could always return a list.
#   Or just always return a dict (I think that's cleaner)
def parse_msg(msg: McapROS2Message) -> dict | list[dict]:
    # NOTE: If returning a list, it should be a list
    # of stackable dicts, ie. of the same structure

    # We dispatch on schema name rather than type because mcap_ros2
    # dynamically generates message classes (e.g. mcap_ros2._dynamic.CameraInfo),
    # making standard type-based dispatch (e.g. singledispatch) impractical.
    parser = _parser_registry.get(msg.schema.name)
    if parser is None:
        registered = ", ".join(sorted(_parser_registry.keys()))
        raise ValueError(
            f"No parser registered for schema: {msg.schema.name}. "
            f"Registered schemas: {registered}"
        )

    parsed = parser(msg.ros_msg)
    if isinstance(parsed, list):
        return [
            {
                **base_message_parser(msg, include_ros_msg=False),
                **r,
            }
            for r in parsed
        ]

    return {
        **base_message_parser(msg, include_ros_msg=False),
        **parsed,
    }


# Could be wrapped in a callable class, but kept in the style of singledispatch
parse_msg.registry = _parser_registry


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Timestamp parsing
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def _parse_timestamps(msg: McapROS2Message) -> dict:
    """Parses the publish and log time from a Mcap ROS2 message.

    Also parses the header timestamp if it exists.

    Return
        dict: A dictionary containing the timestamps.
        - 'publish_time' - When the message was published by the node.
            Set by the publisher when publish() is called.
        - 'log_time' - When the message was written to the bag file by the recorder.
            This is when rosbag2 actually captured it.
        - 'message_time' - Application-specific timestamp in the
            message's Header.stamp field. Typically set by the publisher to indicate
            when the data was generated (e.g., when a sensor reading was taken).
    """

    times_dict = {
        "publish_time": np.int64(msg.publish_time_ns),
        "log_time": np.int64(msg.log_time_ns),
    }
    if hasattr(msg.ros_msg, "header") and hasattr(msg.ros_msg.header, "stamp"):
        t = np.int64(
            msg.ros_msg.header.stamp.sec * 10**9 + msg.ros_msg.header.stamp.nanosec
        )
        times_dict["message_time"] = t

    return times_dict


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Registered parsers
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_IMAGE_ENCODINGS = {
    "rgb8": (np.uint8, 3),
    "rgba8": (np.uint8, 4),
    "bgr8": (np.uint8, 3),
    "bgra8": (np.uint8, 4),
    "mono8": (np.uint8, 1),
    "mono16": (np.uint16, 1),
    "16UC1": (np.uint16, 1),
    "32FC1": (np.float32, 1),
}


@register_parser("sensor_msgs/msg/Image")
def parse_image_msg(ros_msg) -> dict:
    """Parses a ROS2 Image message, returning the image as a np array."""
    # > https://github.com/ros2/common_interfaces/blob/rolling/sensor_msgs/msg/Image.msg
    encoding = ros_msg.encoding

    if encoding not in _IMAGE_ENCODINGS:
        raise ValueError(f"Unsupported image encoding: {encoding}")

    dtype, channels = _IMAGE_ENCODINGS[encoding]
    data = np.frombuffer(bytes(ros_msg.data), dtype=dtype)

    if channels == 1:
        image = data.reshape((ros_msg.height, ros_msg.width))
    else:
        image = data.reshape((ros_msg.height, ros_msg.width, channels))

    # Convert BGR variants to RGB
    if encoding == "bgr8":
        image = image[:, :, ::-1]
        encoding = "rgb8"
    elif encoding == "bgra8":
        image = image[:, :, [2, 1, 0, 3]]
        encoding = "rgba8"

    return {
        "frame_id": ros_msg.header.frame_id,
        "height": ros_msg.height,
        "width": ros_msg.width,
        "encoding": encoding,
        "data": image,
    }


@register_parser("sensor_msgs/msg/CameraInfo")
def parse_camera_info_msg(ros_msg) -> dict:
    """Parses a ROS2 CameraInfo message."""
    # > https://docs.ros.org/en/noetic/api/sensor_msgs/html/msg/CameraInfo.html
    # > https://github.com/ros2/common_interfaces/blob/rolling/sensor_msgs/msg/CameraInfo.msg

    try:
        roi = ros_msg.roi
        roi_dict = {
            "x_offset": roi.x_offset,
            "y_offset": roi.y_offset,
            "height": roi.height,
            "width": roi.width,
            "do_rectify": roi.do_rectify,
        }
    except AttributeError:
        roi_dict = {}

    info = {
        "frame_id": ros_msg.header.frame_id,
        "height": ros_msg.height,
        "width": ros_msg.width,
        "distortion_model": ros_msg.distortion_model,
        "D": np.array(getattr(ros_msg, "d", []) or getattr(ros_msg, "D", [])),
        "K": np.array(getattr(ros_msg, "k", []) or getattr(ros_msg, "K", [])),
        "R": np.array(getattr(ros_msg, "r", []) or getattr(ros_msg, "R", [])),
        "P": np.array(getattr(ros_msg, "p", []) or getattr(ros_msg, "P", [])),
        "binning_x": getattr(ros_msg, "binning_x", 1),
        "binning_y": getattr(ros_msg, "binning_y", 1),
        "roi": roi_dict,
    }
    return info


def _parse_quaternion(q) -> np.ndarray:
    return np.array([q.x, q.y, q.z, q.w])


def _parse_xyz(v) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


def _parse_transform(t) -> dict:
    return {
        "translation": _parse_xyz(t.translation),
        "quaternion": _parse_quaternion(t.rotation),
    }


def _parse_pose(p) -> dict:
    return {
        "translation": _parse_xyz(p.position),
        "quaternion": _parse_quaternion(p.orientation),
    }


def _parse_transform_stamped(ts) -> dict:
    return {
        **_parse_transform(ts.transform),
        "frame_id": ts.header.frame_id,
        "child_frame_id": ts.child_frame_id,
    }


@register_parser("geometry_msgs/msg/PoseStamped")
def parse_pose_stamped_msg(ros_msg) -> dict:
    """Parses a ROS2 PoseStamped message."""
    return {
        "frame_id": ros_msg.header.frame_id,
        "child_frame_id": None,
        **_parse_pose(ros_msg.pose),
    }


# TODO: Don't return a list. Maybe stack the dicts here.
#   What if transforms is []?
@register_parser("tf2_msgs/msg/TFMessage")
def parse_tf_message_msg(ros_msg) -> list[dict]:
    """Parses a ROS2 TFMessage containing a list of TransformStamped."""
    return {"transforms": [_parse_transform_stamped(ts) for ts in ros_msg.transforms]}
