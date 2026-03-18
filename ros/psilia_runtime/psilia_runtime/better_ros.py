import inspect
from functools import wraps
from typing import get_type_hints
import re

import rclpy # type: ignore
from rclpy.node import Node # type: ignore
from rcl_interfaces.msg import SetParametersResult # type: ignore
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument # type: ignore
from launch.substitutions import LaunchConfiguration # type: ignore

#
#   Better launch script
#
def better_launch(func):
    """Decorator that auto-declares launch arguments from a function's signature.

    Each parameter becomes a DeclareLaunchArgument and a LaunchConfiguration
    substitution, which are passed into the decorated function. Parameters
    without defaults are declared as required; parameters with defaults use
    str(default) as the launch argument default value.

    The decorated function must be named `generate_launch_description` and
    must return a LaunchDescription. The declared arguments are prepended to
    its entities.

    Example::

        @better_launch
        def generate_launch_description(
            camera_type="zed2i",
            fps=30,
        ):
            return LaunchDescription([
                Node(
                    package="psilia_runtime",
                    executable="camera_node",
                    parameters=[{"camera_type": camera_type, "fps": fps}],
                )
            ])

    Equivalent to manually writing::

        def generate_launch_description():
            camera_type = LaunchConfiguration("camera_type")
            fps = LaunchConfiguration("fps")
            return LaunchDescription([
                DeclareLaunchArgument("camera_type", default_value="zed2i"),
                DeclareLaunchArgument("fps", default_value="30"),
                Node(...),
            ])
    """
    sig = inspect.signature(func)
    kwargs = {}
    launch_arguments = []
    for name, param in sig.parameters.items():
        kwargs[name] = LaunchConfiguration(name)

        if param.default is inspect.Parameter.empty or param.default is None:
            launch_arguments.append(DeclareLaunchArgument(
                    name,
                    description=f"Launch argument for {name}",
            ))
        else:
            launch_arguments.append(DeclareLaunchArgument(
                    name,
                    default_value=str(param.default),
                    description=f"Launch argument for {name}",
            ))


    def generate_launch_description():
        ld = func(**kwargs)
        return LaunchDescription(launch_arguments + list(ld.entities))


    return generate_launch_description







#
#   Better Node
#
_PATTERN = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
def to_snake_case(name):
    return _PATTERN.sub('_', name).lower()


class ROSValue:
    """Annotation marker. Parameter is declared, read once at startup, and handed
    down as a plain value. Use for params that don't change after node init."""
    pass



def better_node_2(cls):
    """Decorator that handles ROS 2 node initialization boilerplate.

    Owns __init__ entirely — calls Node.__init__ with an auto-generated node
    name (snake_case of the class name), declares and reads all ROSValue-annotated
    parameters, then calls __node_init__ with the resolved plain values.

    For dynamic parameter updates, add your own add_on_set_parameters_callback
    in __node_init__.

    Usage::

        @better_node
        class MyCameraNode(Node):

            def __node_init__(
                    self,
                    camera_type: ROSValue = "zed2i",
                    fps: ROSValue = 30,
                ):
                self.camera_type = camera_type  # plain str
                self.fps = fps                  # plain int
    """
    if not Node in cls.__bases__:
        raise TypeError("better_node can only be applied to direct subclasses of rclpy.node.Node")

    post_init = cls.__node_init__
    hints = get_type_hints(post_init)

    def new_init(self, **kwargs):
        # ROS 2 nodes don't take meaningful positional args — kwargs only.
        # better_node owns __init__ entirely; user logic goes in __node_init__.
        bound = inspect.signature(post_init).bind(self, **kwargs)
        bound.apply_defaults()
        rest_kwargs = bound.kwargs

        super(cls, self).__init__(to_snake_case(cls.__name__))  # ROS middleware ready after this

        for name, val in rest_kwargs.items():
            if hints.get(name) is ROSValue:
                self.declare_parameter(name, val)
                rest_kwargs[name] = self.get_parameter(name).value

        post_init(self, **rest_kwargs)

    cls.__init__ = new_init

    return cls


# TODO: consider allowing an optional node name to be passed to the decorator,
#       e.g. @node("my_camera_node"), falling back to to_snake_case(cls.__name__)
#       if not provided. Would require the decorator to handle both @node and @node("name").
def better_node(cls):
    """Decorator that handles ROS 2 node initialization boilerplate.

    Owns __init__ entirely — calls Node.__init__ with an auto-generated node
    name (snake_case of the class name), declares and reads all class-level
    ROSValue-annotated attributes, assigns them as instance attributes, then
    calls __node_init__ with no extra parameters.

    Usage::

        @better_node
        class MyCameraNode(Node):
            camera_type: ROSValue = "zed2i"
            fps: ROSValue = 30

            def __node_init__(self):
                self.timer = self.create_timer(1.0 / self.fps, self.tick)
    """
    if not Node in cls.__bases__:
        raise TypeError("better_node can only be applied to direct subclasses of rclpy.node.Node")

    class_hints = get_type_hints(cls)

    def new_init(self):
        super(cls, self).__init__(to_snake_case(cls.__name__))

        for name, hint in class_hints.items():
            if hint is ROSValue:
                default = getattr(cls, name)
                self.declare_parameter(name, default)
                setattr(self, name, self.get_parameter(name).value)

        cls.__node_init__(self)

    cls.__init__ = new_init

    return cls


#
#   Example usage
#
@better_node
class MyBetterNode(Node):

    def __node_init__(
            self,
            robot_name: ROSValue = "default_robot",
            refresh_rate: ROSValue = 10,
        ):
        self.robot_name = robot_name  # plain str
        self.refresh_rate = refresh_rate  # plain int
        self.timer = self.create_timer(1.0 / self.refresh_rate, self.tick)

    def tick(self):
        self.get_logger().info(f"Robot: {self.robot_name}")




#
#   Experimental
#
class ROSParam:
    """Annotation marker. Parameter is declared and handed down as a cached live
    handle. Value is updated automatically via a parameter callback registered by
    better_node — cheap to read, stays current without IPC on every access."""
    def __init__(self, value):
        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v


def better_node_experimental(cls):
    """Decorator that handles ROS 2 node initialization boilerplate.

    Owns __init__ entirely — calls Node.__init__ with an auto-generated node
    name (snake_case of the class name), wires up ROSParam-annotated parameters,
    then calls __node_init__ with the resolved params. The user never writes
    __init__ or calls super().__init__().

    Design decisions:
    - __node_init__ instead of __init__: makes it unambiguous that the decorator
      owns initialization. Mirrors the dataclasses pattern.
    - Node name from class name: equivalent to hardcoding it in super().__init__(),
      which is standard ROS 2 practice. The launch file name= field still overrides
      it at the middleware level.
    - Direct subclass only: super(cls, self).__init__() must hit Node.__init__
      directly. If an intermediate subclass exists, Node.__init__ could be called
      twice, reinitializing the ROS middleware. Restricted to direct subclasses
      to keep initialization safe and predictable.
    - Annotation-driven, not instance-driven: plain values as defaults avoids the
      mutable default argument problem. The annotation marks intent — ROSValue for
      a one-time read (hands down the raw value), ROSParam for a cached live handle
      (hands down a ROSParam instance whose .value is kept current via a parameter
      callback registered automatically by better_node). Cheap to read, no IPC on
      every access. Fresh instances are created per parameter per node instantiation.

    Usage::

        @better_node
        class MyCameraNode(Node):

            def __node_init__(
                    self,
                    camera_type: ROSValue = "zed2i",  # read once, plain str
                    fps: ROSParam = 30,                # live handle
                ):
                self.camera_type = camera_type
                self.timer = self.create_timer(1.0 / fps.value, self.tick)

    Equivalent to::

        class MyCameraNode(Node):
            def __init__(self):
                super().__init__("my_camera_node")
                self.declare_parameter("camera_type", "zed2i")
                self.declare_parameter("fps", 30)
                self.camera_type = self.get_parameter("camera_type").value
                self._fps = self.get_parameter  # live via get_parameter each access
                self.timer = self.create_timer(1.0 / self.get_parameter("fps").value, self.tick)
    """
    if not Node in cls.__bases__:
        raise TypeError("better_node can only be applied to direct subclasses of rclpy.node.Node")

    post_init = cls.__node_init__
    hints = get_type_hints(post_init)

    def new_init(self, **kwargs):
        # ROS 2 nodes don't take meaningful positional args — kwargs only.
        # better_node owns __init__ entirely; user logic goes in __node_init__.
        bound = inspect.signature(post_init).bind(self, **kwargs)
        bound.apply_defaults()
        rest_kwargs = bound.kwargs

        super(cls, self).__init__(to_snake_case(cls.__name__))  # ROS middleware ready after this

        ros_params = {}  # name -> ROSParam instance, kept for callback updates
        for name, val in rest_kwargs.items():
            if hints.get(name) is ROSValue:
                self.declare_parameter(name, val)
                rest_kwargs[name] = self.get_parameter(name).value
            elif hints.get(name) is ROSParam:
                self.declare_parameter(name, val)
                ros_params[name] = ROSParam(self.get_parameter(name).value)
                rest_kwargs[name] = ros_params[name]

        if ros_params:
            def on_params_changed(params):
                for p in params:
                    if p.name in ros_params:
                        ros_params[p.name].value = p.value
                return SetParametersResult(successful=True)

            self.add_on_set_parameters_callback(on_params_changed)

        post_init(self, **rest_kwargs)

    cls.__init__ = new_init

    return cls

#
#   Example usage of better_node_experimental
#
@better_node_experimental
class MyBetterNodeExperimental(Node):

    def __node_init__(
            self,
            robot_name: ROSValue = "default_robot",  # plain str, read once at init
            refresh_rate: ROSParam = 10,              # cached handle, updated via ros2 param set
        ):
        self.robot_name = robot_name
        self.refresh_rate = refresh_rate
        self.timer = self.create_timer(0.1, self.tick)

    def tick(self):
        # refresh_rate.value reflects any ros2 param set changes at runtime
        self.get_logger().info(f"Robot: {self.robot_name}, rate: {self.refresh_rate.value}")
