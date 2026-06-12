"""
Camera core module containing intrinsics, projections, and distortion models.

Notation:
 - Screen coordinates (u,v): Pixel coordinates of the image plane.
 - Camera coordinates (x,y,z): Coordinates of the camera frame.
 - "Normalized" screen coordinates (x',y'): Coordinates of the image plane,
   normalized by the depth z (z is the z-coordinate of the camera frame).
   Sometimes (x,y) is used instead (if no z is present, we assume it's
   normalized coordinates):
    - Relation to camera coordinates: (x',y') = (x/z,y/z)
    - Relation to screen coordinates: (u,v,1)^T = K * (x',y',1)^T.
    - Relation to camera coordinates: (x,y,z)^T = K^{-1} * (u,v,1)^T.
- Depth (z): We refer to the z-coordinate of the camera frame as the depth.
"""

from typing import Any, Self, TypeAlias

import jax.numpy as jnp
import numpy as np
import yaml
from jax.tree_util import register_pytree_node_class
from mcap_ros2.reader import McapROS2Message

from psilia.transforms.transform import Transform
from psilia.utils import load_yaml, save_yaml
from psilia.data.mcap import parse_camera_info_msg

Array: TypeAlias = Any
Points2D: TypeAlias = Any
Points3D: TypeAlias = Any
Point3D: TypeAlias = Any
Float: TypeAlias = Any

__all__ = [
    "CameraIntrinsics",
    "_pinhole",
    "_pinhole_jacobian",
    "camera_from_screen_and_depth",
    "camera_projection_matrix",
    "compute_uv_grid",
    "homogeneous",
    "normalized_from_sensor",
    "pixel_centers_from_shape",
    "project",
    "render_naively",
    "screen_from_camera",
    "sensor_from_normalized",
    "unproject",
]


# # # # # # # # # # # # # # # # # #
#
#   Camera Intrinsics
#
# # # # # # # # # # # # # # # # # #
@register_pytree_node_class
class CameraIntrinsics:
    """
    Camera intrinsics.

    Note: This class mimics the structure of the calibration output from kalibr.
    > https://github.com/ethz-asl/kalibr/wiki/yaml-formats
    """

    def __init__(
        self,
        intrinsics: Array,
        distortion_coeffs: Array,
        camera_model: str = "pinhole",
        distortion_model: str = "radtan",
        width: int = -1,
        height: int = -1,
        camera_name: str = "",
    ):
        self.intrinsics = intrinsics
        self.distortion_coeffs = distortion_coeffs
        self.camera_model = camera_model
        self.distortion_model = distortion_model
        self.width = width
        self.height = height
        self.camera_name = camera_name

        # Create a 2D pixel grid
        self._uv_grid = pixel_centers_from_shape((self.height, self.width))
        self._uv_grid_distorted = distort_sensor(
            self._uv_grid.reshape(-1, 2), self
        ).reshape(self.height, self.width, 2)

        # Bounding box in sensor coordinates that lands
        # within image bounds when distorted.
        uvs = undistort_image(self._uv_grid, self).reshape(-1, 2)
        delta = 10.0
        self._preimage_distorted = jnp.array(
            [
                [uvs[:, 0].min() - delta, uvs[:, 1].min() - delta],
                [uvs[:, 0].max() + delta, uvs[:, 1].max() + delta],
            ]
        )

    def jax(self):
        """Ensure that the intrinsics and distortion coefficients are JAX arrays."""
        self.intrinsics = jnp.array(self.intrinsics)
        self.distortion_coeffs = jnp.array(self.distortion_coeffs)
        self.width = jnp.array(self.width)
        self.height = jnp.array(self.height)
        return self

    # Jax Pytree Registration
    def tree_flatten(self):
        return (
            (self.intrinsics, self.distortion_coeffs),
            {
                "camera_model": self.camera_model,
                "distortion_model": self.distortion_model,
                "camera_name": self.camera_name,
                "width": self.width,
                "height": self.height,
            },
        )

    # Jax Pytree Registration
    @classmethod
    def tree_unflatten(cls, aux_data, children):
        return cls(*children, **aux_data)

    @property
    def resolution(self):
        """Resolution of the camera in `x` (width) and `y` (height) direction."""
        return self.width, self.height

    @property
    def image_shape(self):
        """Image shape (height, width)."""
        return (self.height, self.width)

    @property
    def w(self):
        return self.width

    @property
    def h(self):
        return self.height

    @property
    def fx(self):
        return self.intrinsics[0]

    @property
    def fy(self):
        return self.intrinsics[1]

    @property
    def cx(self):
        return self.intrinsics[2]

    @property
    def cy(self):
        return self.intrinsics[3]

    @property
    def camera_matrix(self):
        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]]
        )

    @property
    def K(self):
        return self.camera_matrix

    @property
    def d(self):
        return self.distortion_coeffs

    def as_dict(self):
        return {
            "camera_name": self.camera_name,
            "intrinsics": {
                "fx": float(self.fx),
                "fy": float(self.fy),
                "cx": float(self.cx),
                "cy": float(self.cy),
            },
            "distortion_coeffs": np.array(self.distortion_coeffs).tolist(),
            "distortion_model": self.distortion_model,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            intrinsics=jnp.array(
                [
                    data["intrinsics"]["fx"],
                    data["intrinsics"]["fy"],
                    data["intrinsics"]["cx"],
                    data["intrinsics"]["cy"],
                ]
            ),
            distortion_coeffs=jnp.array(data["distortion_coeffs"]),
            distortion_model=data["distortion_model"],
            width=data["width"],
            height=data["height"],
            camera_name=data["camera_name"],
        )

    def save(self, fname):
        return save_yaml(self.as_dict(), fname)

    @classmethod
    def load(cls, fname):
        data = load_yaml(fname)
        return cls.from_dict(data)

    @classmethod
    def from_kalibr(cls, yaml_path: str, camera_name: str = "cam0"):
        """
        Load camera intrinsics from a Kalibr YAML file.

        Args:
            yaml_path: Path to the Kalibr YAML file.
            camera_name: Name of the camera to load (default: 'cam0').

        Returns:
            CameraIntrinsics: Camera intrinsics object.
        """
        with open(yaml_path) as file:
            data = yaml.safe_load(file)

        if camera_name not in data:
            msg = f"Expected camera name {camera_name} in the YAML file, but found {data.keys()}."
            raise ValueError(msg)

        cam_dict = {
            "intrinsics": jnp.array(data[camera_name]["intrinsics"]),
            "camera_model": data[camera_name]["camera_model"],
            "distortion_model": data[camera_name]["distortion_model"],
            "distortion_coeffs": jnp.array(data[camera_name]["distortion_coeffs"]),
            "width": data[camera_name]["resolution"][0],
            "height": data[camera_name]["resolution"][1],
            "camera_name": camera_name,
        }

        return cls(**cam_dict)

    def resize(self, factor: float) -> Self:
        return CameraIntrinsics(
            self.intrinsics * factor,
            self.distortion_coeffs,
            self.camera_model,
            self.distortion_model,
            int(self.width * factor),
            int(self.height * factor),
            self.camera_name,
        )

    @classmethod
    def from_camera_info_dict(cls, info: dict) -> Self:
        # TODO: Define what a camera info dict should look like.
        assert "k" in info or "K" in info, "K or k must be present in the info dict"
        assert "d" in info or "D" in info, "D or d must be present in the info dict"

        # "plumb_bob" - a simple model of radial and tangential distortion
        # > https://docs.ros.org/en/api/sensor_msgs/html/msg/CameraInfo.html
        # if info["distortion_model"] != "plumb_bob":
        #     warn(
        #         f"Unknown distortion model: '{info['distortion_model']}'", stacklevel=1
        #     )

        def get_value(d, keys, default=None):
            for key in keys:
                if key in d:
                    return d[key]
            return default

        camera_name = get_value(info, ["frame_id", "camera_name"], "")
        K = get_value(info, ["K", "k"], None)
        D = get_value(info, ["D", "d"], None)
        K = jnp.array(K).reshape(3, 3)
        D = jnp.array(D).reshape(-1)

        camera_name = info.get("frame_id", info.get("camera_name", ""))

        return cls(
            camera_name=camera_name,
            camera_model="pinhole",
            distortion_model=info["distortion_model"],
            intrinsics=jnp.array([K[0, 0], K[1, 1], K[0, 2], K[1, 2]]),
            distortion_coeffs=D,
            width=info["width"],
            height=info["height"],
        )

    @classmethod
    def from_camera_info_msg(cls, msg: McapROS2Message):
        assert msg.schema.name == "sensor_msgs/msg/CameraInfo", (
            f"Expected CameraInfo message, but got {msg.schema.name}"
        )
        info = parse_camera_info_msg(msg)
        return cls.from_camera_info_dict(info)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        s = (
            "CameraIntrinsics(\n"
            + f"  intrinsics={self.intrinsics},\n"
            + f"  distortion_model='{self.distortion_model}',\n"
            + f"  distortion_coeffs={self.distortion_coeffs},\n"
            + f"  width={self.width},\n"
            + f"  height={self.height},\n"
            + f"  camera_model='{self.camera_model}'"
        )

        if self.camera_name != "":
            s += f",\n  camera_name={self.camera_name}"

        s += "\n)"
        return s


# # # # # # # # # # # # # # # # # #
#
#  Pinhole Camera
#
# # # # # # # # # # # # # # # # # #
# TODO: Should we have a Camera class?


# TODO: this should go to vision.camera,
#   or even as a method of CameraIntrinsics
def compute_uv_grid(intr, flat=False, indexing="uv", offset=0.5):
    """
    Computes a grid of sensor/pixel-coordinates.

    If indexing is `ij` the unflattened
    uv/xy-indexing:
        grid[u, v] = [u,v]
        grid[x, y] = [x,y]
        grid[3,7] = [3.5, 7.5]

    ij-indexing:
        grid[i,j] = [j, i]
    """
    if indexing in {"uv", "xy"}:
        u, v = jnp.mgrid[: intr.w, : intr.h]
    elif indexing == "ij":
        v, u = jnp.mgrid[: intr.h, : intr.w]
    else:
        raise ValueError(f"Unknown indexing: {indexing}")

    uv_grid = jnp.stack([u, v], axis=-1) + offset
    if flat:
        uv_grid = uv_grid.reshape(-1, 2)
    return uv_grid


# TODO: Make a version of this with a camera_intrinsics as an input
def pixel_centers_from_shape(img_shape: tuple[int, int]) -> Points2D:
    """
    Returns a 2D-array of sensor coordinates `uv` of the centers
    of each pixel of an image. The i,j-th entry are the sensor coordinates u,v
    of the center of the pixel at row i and column j.

    ```
    uvs = jnp.array([
        [[0., 0.], [1., 0.]],
        [[0., 1.], [1., 1.]],
    ]) + 0.5
    ```
    Args:
        `img_shape`: (H,W) shape of an image.

    Returns:
        (H,W,2) array of sensor coordinates of the centers of each image pixel.
    """
    v, u = jnp.mgrid[: img_shape[0], : img_shape[1]]
    return jnp.stack([u, v], axis=-1) + 0.5


def camera_projection_matrix(camera_transform: Transform, intr: CameraIntrinsics):
    """
    Compute the camera projection matrix `P = K[R^T | -R^T t]`,
    mapping 3D points in the world frame to 2D points in the image plane.

    ```
        [u', v', w]^T = P * [x, y, z, 1]^T
        [u,v] = [u', v'] / w
    ```

    Args:
        camera_transform: Camera transform.
        intr: Camera intrinsics.

    Returns:
        Camera projection matrix.
    """
    cam_inv = camera_transform.inv()
    return intr.K @ jnp.concatenate([cam_inv.R, cam_inv.t[:, None]], axis=-1)


def normalized_from_sensor(uvs: Points2D, intr: CameraIntrinsics) -> Points2D:
    """Convert sensor coordinates `uv` to normalized coordinates `xy`."""
    fx, fy, cx, cy = intr.intrinsics
    u, v = uvs[..., 0], uvs[..., 1]
    x = (u - cx) / fx
    y = (v - cy) / fy
    return jnp.stack([x, y], axis=-1)


def sensor_from_normalized(xys: Points2D, intr: CameraIntrinsics) -> Points2D:
    """Convert normalized coordinates `xy` to sensor coordinates `uv`."""
    fx, fy, cx, cy = intr.intrinsics
    x, y = xys[..., 0], xys[..., 1]
    u = x * fx + cx
    v = y * fy + cy
    return jnp.stack([u, v], axis=-1)


def _pinhole(xyzs: Points3D, fx: Float, fy: Float, cx: Float, cy: Float) -> Points2D:
    """
    Pinhole projection without distortion.

    Maps to sensor coordintaes `uv` from camera coordinates `xyz`, which are
    defined by $(u,v) = (u'/z,v'/z)$, where
    $$
        (u', v', z)^T = K * (x, y, z)^T,
    $$
    and $K$ is the camera matrix.

    Args:
        `xyzs`: (...,3) array of camera coordinates.
        `fx`: Focal length in x-direction.
        `fy`: Focal length in y-direction.
        `cx`: Principal point in x-direction.
        `cy`: Principal point in y-direction.

    Returns:
        `uvs`: (...,2) array of sensor coordinates.
    """
    xs, ys, zs = xyzs[..., 0], xyzs[..., 1], xyzs[..., 2]
    x_normalized = xs / zs
    y_normalized = ys / zs
    us = x_normalized * fx + cx
    vs = y_normalized * fy + cy
    return jnp.stack([us, vs], axis=-1)


def _pinhole_jacobian(
    xyz: Point3D, fx: Float, fy: Float, cx: Float, cy: Float
) -> Array:
    """
    Jacobian of the pinhole projection.

    Args:
        `xyz`: (...,3) array of camera coordinates.
        `fx`: Focal length in x-direction.
        `fy`: Focal length in y-direction.
        `cx`: Principal point in x-direction.
        `cy`: Principal point in y-direction.

    Returns:
        `J`: (2,3) Jacobian of the pinhole projection.
    """
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]

    return jnp.array([[fx / z, 0, -fx * x / z**2], [0, fy / z, -fy * y / z**2]])


def screen_from_camera(xyz: Points3D, intr: CameraIntrinsics) -> tuple[Points2D, Array]:
    """
    Pinhole projection without distortion.

    Maps to sensor coordintaes `uv` from camera coordinates `xyz`, which are
    defined by $(u,v) = (u'/z,v'/z)$, where
    $$
        (u', v', z)^T = K * (x, y, z)^T,
    $$
    and $K$ is the camera matrix.

    Args:
        `xyz`: (...,3) array of camera coordinates.
        `intr`: Intrinsics.

    Returns:
        uv: (...,2) array of screen coordinates.
        valid: (...) array of boolean values indicating
            whether the point is within the image bounds.
    """
    fx, fy, cx, cy = intr.intrinsics
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    x_normalized = x / z
    y_normalized = y / z
    u = x_normalized * fx + cx
    v = y_normalized * fy + cy

    # TODO: Add clipping; near and far planes and what not
    # Clip to positive depth
    zmask = z > 0.0

    # Project to sensor and
    # check if within image bounds
    uv = jnp.stack([u, v], axis=-1)
    imask = (
        (0 < uv[..., 0])
        * (uv[..., 0] < intr.width)
        * (0 < uv[..., 1])
        * (uv[..., 1] < intr.height)
    )

    # Combine the masks
    valid = (zmask * imask).astype(bool)

    return uv, valid


def camera_from_screen_and_depth(
    uv: Points2D, z: Array, intr: CameraIntrinsics
) -> Points3D:
    """
    Returns camera coordinates `xyz` from sensor coordinates `uv`, and depth measurements `z`.
    These are related by the camera matrix $K$ as follows:
    $$
        (x, y, z)^T = K^{-1} * (z*u, z*v, z)^T.
    $$.

    Args:
        `uv`: (...,2) array of  sensor coordinates.
        `z`:  (...,)  array of depth measurements.
        `intrinsics`: Intrinsic camera calibration.

    Returns:
        (...,3) array of camera coordinates.
    """
    fx, fy, cx, cy = intr.intrinsics
    u, v = uv[..., 0], uv[..., 1]
    x = (u - cx) / fx
    y = (v - cy) / fy
    return jnp.stack([x, y, jnp.ones_like(x)], axis=-1) * z[..., None]


project = screen_from_camera


def unproject(arr: Array, intr: CameraIntrinsics) -> Array:
    """
    Unproject from screen to camera coordinates.

    Args:
        `arr`: (N,3) array of u,v,z coordinates,
            (N,2) array of u,v coordinates,
            or (H,W,1) array of depth images.
        `intr`: Intrinsics.

    Returns:
        `xyz`: (N,3) or (H,W,3) array of camera coordinates.
    """
    if len(arr.shape) == 3 and arr.shape[-1] == 1:
        # Depth Image (H,W,1)
        uv = pixel_centers_from_shape(arr.shape[:-1])
        z = arr[..., -1]
    elif arr.shape[-1] == 2:
        # UV Array (N,2)
        uv = arr
        z = jnp.ones_like(uv[..., 0])
    elif arr.shape[-1] == 3:
        # UVZ Array (N,3)
        uv = arr[:, :2]
        z = arr[:, 2]
    else:
        raise ValueError(
            f"Expected 1,2 or 3 channels in the last dimension, "
            f"but got array with shape {arr.shape}"
        )
    return camera_from_screen_and_depth(uv, z, intr)


def camera_from_screen(uv: Points2D, intr: CameraIntrinsics) -> Points3D:
    z = jnp.ones(uv.shape[:-1])
    return camera_from_screen_and_depth(uv, z, intr)


# # # # # # # # # # # # # # # # # #
#
#   `Radtan` Distortion
#
# # # # # # # # # # # # # # # # # #
def distort_normalized(xys: Points2D, intr: CameraIntrinsics) -> Points2D:
    """
    Distort normalized coordinates `xys` using the `radtan` distortion model.

    Args:
        xys: Nx2 array of distorted normalized coordinates
        intr: IntrinsicCalibration

    Returns:
        Nx2 array of undistorted normalized coordinates
    """
    x, y = xys[..., 0], xys[..., 1]
    k1, k2, p1, p2 = intr.distortion_coeffs[:4]

    # Radial distortion
    r2 = x * x + y * y
    r4 = r2 * r2
    radial = 1 + k1 * r2 + k2 * r4

    # Tangential distortion
    dx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
    dy = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y

    # Apply distortion
    x_dist = x * radial + dx
    y_dist = y * radial + dy

    return jnp.stack([x_dist, y_dist], axis=-1)


def distort_sensor(uvs: Points2D, intr: CameraIntrinsics) -> Points2D:
    """
    Distort sensor coordinates `uvs` using the `radtan` distortion model.

    Args:
        uvs: Nx2 array of sensor coordinates
        intr: IntrinsicCalibration

    Returns:
        Nx2 array of distorted sensor coordinates
    """
    return sensor_from_normalized(
        distort_normalized(normalized_from_sensor(uvs, intr), intr), intr
    )


def undistort_image(im_distorted: Array, intr: CameraIntrinsics) -> Array:
    """
    Approximate undistortion (`radtan` distortion model) of an image-like array
    using the camera intrinsics.

    Args:
        im_distorted: Distorted image-like array.
        intr: Camera intrinsics.

    Returns:
        Undistorted image-like array.
    """
    uvs_distorted = intr._uv_grid_distorted.reshape(-1, 2)
    # TODO: Add inital values
    im = im_distorted[uvs_distorted[:, 1].astype(int), uvs_distorted[:, 0].astype(int)]
    im = im.reshape(intr.height, intr.width, -1)
    return im


# # # # # # # # # # # # # # # # # #
#
#   Utilities
#
# # # # # # # # # # # # # # # # # #
def homogeneous(x: jnp.ndarray) -> jnp.ndarray:
    """
    Adds a homogeneous coordinate to an array along the last dimension.

    Args:
        x: Array of shape (..., N).

    Returns:
        Array of shape (..., N+1).
    """
    return jnp.concatenate([x, jnp.ones_like(x[..., [0]])], axis=-1)


hom = homogeneous


def camera_matrix_from_flat(intr_vector):
    fx, fy, cx, cy = intr_vector
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])


# TODO: Check if we have an off by one error here
# NOTE: This is more a quick and dirty reality check
# than a proper rendering function.
def render_naively(xs, vs, intr, shape, down=1, fill_value=0.0):
    """
    Naively renders a point cloud on an image. ...

    Basically projects on the image, for each pixel
    keeps the value of the closest point.

    Args:
        xs: (N, 3) array of camera coordinates.
        vs: (N, K) array of point colors but
            could depth or some other feature as well.
        intr: Intrinsic camera calibration.
        shape: (H, W) shape of the image.
        down: Downsampling factor.

    Returns:
        (H, W, K) array of rendered points.
    """
    if len(vs.shape) == 1:
        vs = vs[..., None]

    # Create pixel bins of the desired shape and pre-filled
    shape = (shape[0] // down, shape[1] // down, vs.shape[-1])
    b = jnp.full(shape, fill_value)

    # Project points to the image plane and sort by depth
    # Put invalid points at infinity
    uvs, valid = screen_from_camera(xs, intr)
    zs = jnp.where(valid, xs[:, 2], jnp.inf)
    perm = jnp.argsort(zs)[::-1]

    # Sort points by depth
    # and replace non valid values with fill value
    uvs = uvs[perm]
    uvs = uvs / down
    vs = jnp.where(valid[:, None], vs, fill_value)[perm]

    # Get pixel indices and set values
    ii = jnp.clip(uvs[:, 1], 0, shape[0]).astype(int)
    jj = jnp.clip(uvs[:, 0], 0, shape[1]).astype(int)
    b_ = b.at[ii, jj, :].set(vs)
    return b_


def get_padding_mask(uvs: Points2D, padding: int, shape: tuple[int, int]) -> Array:
    """
    Get a mask of valid points that are within a certain padding of the image bounds.
    """
    assert len(shape) == 2, "Image shape must be a tuple of (height, width)"
    h, w = shape
    return (
        (padding < uvs[..., 0])
        * (uvs[..., 0] < w - padding)
        * (padding < uvs[..., 1])
        * (uvs[..., 1] < h - padding)
    )


def get_pixel_values(
    im, xs: Points3D, intr: CameraIntrinsics
) -> tuple[Array, Array, Points2D]:
    """
    Get pixel values from an image for a set of 3D points (in camera coordinates).

    Returns:
        vs: Pixel values (NxC)
        valid: Mask of valid points within image bounds (N,)
        uvs: Sensor coordinates of the 3D points (N, 2)
    """
    # Compute pixel coordinates, and mask of valid points
    # that are in the image
    uvs, valid = screen_from_camera(xs, intr)

    # Clip to image bounds, and round to nearest integer.
    # If we'd use only valid points, we wouldn't need to clip.
    # But for convenience, we'll clip and floor all points.
    uvs_clipped = uvs.clip(np.zeros(2), np.array([im.shape[1] - 1, im.shape[0] - 1]))
    uvs_clipped = np.floor(uvs_clipped).astype(int)

    # Get pixel values
    vs = im[uvs_clipped[:, 1], uvs_clipped[:, 0]]

    return vs, valid, uvs
