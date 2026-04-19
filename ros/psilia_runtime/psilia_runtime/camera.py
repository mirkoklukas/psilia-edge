from collections import namedtuple
from typing import Any, TypeAlias
from pathlib import Path

import cv2
import numpy as np
import yaml
from scipy.spatial.transform import Rotation as Rot

from psilia_runtime.utils import load_yaml, save_yaml

Array: TypeAlias = Any

StereoRectification = namedtuple(
    "StereoRectification",
    [
        "map1_l",
        "map2_l",
        "map1_r",
        "map2_r",
        "R0",
        "R1",
        "P0",
        "P1",
        "Q",
    ],
)
Matrix: TypeAlias = Array
Matrix3x3: TypeAlias = Array
Matrix3x4: TypeAlias = Array
Matrix4x4: TypeAlias = Array

# NOTE: Useful links
# > https://docs.ros.org/en/noetic/api/sensor_msgs/html/msg/CameraInfo.html
# > https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga617b1685d4059c6040827800e72ad2b6


class CameraCalibration:
    """Camera calibration.

    Stores three categories of information:

    1. Distortion model:
       - model: camera model, e.g. "PINHOLE"
       - distortion_model: distortion model, e.g. "RADTAN"
       - distortion_coeffs: model-specific coefficients, e.g. [k1, k2, p1, p2, k3]

    2. Calibration:
       - intrinsics: [fx, fy, cx, cy] — raw camera intrinsics.
       - extrinsics: [tx, ty, tz, qx, qy, qz, qw] — pose relative to parent
         frame (e.g. lead camera). Defines the 3x4 matrix M = [R | t] such
         that the unrectified projection is P = K @ [R | t].
         Defaults to identity.
       - rectification: [qx, qy, qz, qw] — rotation applied to align
         epipolar lines after stereo rectification. None if not rectified.
       - rectified_projection: [fx', fy', cx', cy', Tx, Ty] — rectified
         projection following the ROS2 CameraInfo convention. Encodes the
         non-trivial elements of the 3x4 rectified projection matrix:
             P = [fx'  0   cx'  Tx]
                 [0   fy'  cy'  Ty]
                 [0    0    1    0 ]
         Tx, Ty encode the stereo baseline (Tx = -fx' * B for horizontal
         stereo). They are redundant — derivable from rectification,
         extrinsics, and rectified intrinsics via:
             t_rect = R_rect @ t
             Tx ≈ fx' * t_rect[0],  Ty ≈ fy' * t_rect[1]
         Stored for convenience and ROS2 compatibility. None if not rectified.

    3. Metadata: width, height, name, parent
    """

    def __init__(
        self,
        intrinsics: Array,
        extrinsics: Array | None = None,
        distortion_coeffs: Array | None = None,
        name: str = "",
        model: str = "PINHOLE",
        distortion_model: str = "",
        width: int = -1,
        height: int = -1,
        rectification: Array | None = None,
        rectified_projection: Array | None = None,
        parent: str | None = None,
    ):
        # Distortion model
        self.model = model.upper()
        self.distortion_model = distortion_model.upper()
        self.distortion_coeffs = (
            np.asarray(distortion_coeffs, dtype=np.float64)
            if distortion_coeffs is not None
            else None
        )

        # Metadata
        self.name = name
        self.width = width
        self.height = height
        self.parent = parent

        # Calibration
        self.intrinsics = np.asarray(intrinsics, dtype=np.float64)
        self.rectification = (
            np.asarray(rectification, dtype=np.float64)
            if rectification is not None
            else None
        )
        self.rectified_projection = (
            np.asarray(rectified_projection, dtype=np.float64)
            if rectified_projection is not None
            else None
        )

        if extrinsics is not None:
            self.extrinsics = np.asarray(extrinsics, dtype=np.float64)
        elif self.rectified_projection is not None and self.rectification is not None:
            # Infer translation from rectified projection and rectification.
            # Rotation can't be recovered from a single camera's rectification
            # (needs both cameras), so it defaults to identity.
            fx_r, fy_r, _, _, Tx, Ty = self.rectified_projection
            t_rect = np.array([Tx / fx_r, Ty / fy_r, 0.0])
            R_rect = Rot.from_quat(self.rectification).as_matrix()
            t = R_rect.T @ t_rect
            self.extrinsics = np.concatenate([t, np.array([0.0, 0.0, 0.0, 1.0])])
        else:
            self.extrinsics = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])

        # Derived matrices
        fx, fy, cx, cy = self.intrinsics
        self.intrinsics_matrix = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])

        x = self.extrinsics[:3]
        q = self.extrinsics[3:]
        self.extrinsics_matrix = np.concatenate(
            [Rot.from_quat(q).as_matrix(), x[:, None]], axis=-1
        )

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
    def d(self):
        return self.distortion_coeffs

    @property
    def K(self):
        return self.intrinsics_matrix

    @property
    def P(self):
        return self.intrinsics_matrix @ self.extrinsics_matrix

    @property
    def P_rect(self):
        if self.rectified_projection is None:
            return None
        fx, fy, cx, cy, Tx, Ty = self.rectified_projection
        return np.array(
            [[fx, 0, cx, Tx], [0, fy, cy, Ty], [0, 0, 1, 0]], dtype=np.float64
        )

    @property
    def B(self):
        if self.rectified_projection is None:
            return None
        else:
            fx, fy, cx, cy, Tx, Ty = self.rectified_projection
            return -Tx / fx

    @property
    def x(self):
        return self.extrinsics[:3]

    @property
    def t(self):
        return self.x

    @property
    def q(self):
        return self.extrinsics[3:]

    @property
    def R(self):
        return Rot.from_quat(self.q).as_matrix()

    @property
    def R_rect(self):
        if self.rectification is None:
            return np.eye(3)
        return Rot.from_quat(self.rectification).as_matrix()

    @property
    def res(self):
        return (self.width, self.height)

    def rescale(self, factor: float) -> "CameraCalibration":
        """Return a new CameraCalibration with intrinsics, rectified projection,
        and resolution scaled. Distortion coefficients and extrinsics are unchanged.
        """
        fx, fy, cx, cy = self.intrinsics
        rectified_projection = None
        if self.rectified_projection is not None:
            pfx, pfy, pcx, pcy, Tx, Ty = self.rectified_projection
            rectified_projection = np.array(
                [
                    pfx * factor,
                    pfy * factor,
                    pcx * factor,
                    pcy * factor,
                    Tx * factor,
                    Ty * factor,
                ]
            )
        return CameraCalibration(
            intrinsics=np.array([fx * factor, fy * factor, cx * factor, cy * factor]),
            extrinsics=self.extrinsics.copy(),
            distortion_coeffs=self.distortion_coeffs.copy()
            if self.distortion_coeffs is not None
            else None,
            model=self.model,
            distortion_model=self.distortion_model,
            width=int(self.width * factor),
            height=int(self.height * factor),
            name=self.name,
            rectification=self.rectification.copy()
            if self.rectification is not None
            else None,
            rectified_projection=rectified_projection,
            parent=self.parent,
        )

    FORMAT = "psilia-camera-calibration"

    def as_dict(self, include_header: bool = True):
        def _tolist_or_none(x):
            if x is not None:
                return x.tolist()
            else:
                return None

        d = {}
        if include_header:
            d["header"] = {
                "format": self.FORMAT,
                "resolution": [self.width, self.height],
            }
        d.update({
            "model": self.model,
            "distortion_model": self.distortion_model,
            "intrinsics": self.intrinsics.tolist(),
            "extrinsics": self.extrinsics.tolist(),
            "distortion_coeffs": _tolist_or_none(self.distortion_coeffs),
            "rectification": _tolist_or_none(self.rectification),
            "rectified_projection": _tolist_or_none(self.rectified_projection),
            "width": self.width,
            "height": self.height,
            "name": self.name,
            "parent": self.parent,
        })
        return d

    @classmethod
    def from_camera_info(
        cls, *, frame_id, width, height, distortion_model, D, K, R, P, **kwargs
    ):
        """Camera Calibration from ROS CameraInfo fields.

        > https://docs.ros.org/en/noetic/api/sensor_msgs/html/msg/CameraInfo.html
        """
        K = np.array(K).reshape((3, 3))
        R = np.array(R).reshape((3, 3))
        P = np.array(P).reshape((3, 4))
        return cls(
            name=frame_id,
            width=width,
            height=height,
            distortion_model=distortion_model,
            distortion_coeffs=D,
            intrinsics=np.array([K[0, 0], K[1, 1], K[0, 2], K[1, 2]]),
            rectification=Rot.from_matrix(R).as_quat(),
            rectified_projection=np.array(
                [P[0, 0], P[1, 1], P[0, 2], P[1, 2], P[0, 3], P[1, 3]]
            ),
        )

    @classmethod
    def from_kalibr(cls, yaml_path: str, camera_name: str = "cam0"):
        """
        Load camera intrinsics from a Kalibr calibration-camchain YAML file.

        Args:
            yaml_path: Path to the Kalibr YAML file.
            camera_name: Name of the camera to load (default: 'cam0').

        Returns:
            CameraInfo: Camera intrinsics object.
        """
        with open(yaml_path) as file:
            data = yaml.safe_load(file)

        if camera_name not in data:
            msg = f"Expected camera name {camera_name} in the YAML file, but found {data.keys()}."
            raise ValueError(msg)

        if "T_cn_cnm1" in data[camera_name]:
            # From https://github.com/ethz-asl/kalibr/wiki/yaml-formats
            # > T_cn_cnm1: camera extrinsic transformation, always with respect to the last camera in the chain
            # > (e.g. cam1: T_cn_cnm1 = T_c1_c0, takes cam0 to cam1 coordinates)
            # That means it is a transform
            #   `cam1 <- cam0`,
            # and describes the position of
            #   *camera 0 relative to camera 1*.

            M = np.array(data[camera_name]["T_cn_cnm1"])
            q = Rot.from_matrix(M[:3, :3]).as_quat()
            x = M[:3, 3]
            extrinsics = np.concatenate([x, q])
        else:
            extrinsics = None

        cam_dict = {
            "intrinsics": np.array(data[camera_name]["intrinsics"]),
            "model": data[camera_name]["camera_model"],
            "distortion_model": data[camera_name]["distortion_model"],
            "distortion_coeffs": np.array(data[camera_name]["distortion_coeffs"]),
            "width": data[camera_name]["resolution"][0],
            "height": data[camera_name]["resolution"][1],
            "name": camera_name,
            "extrinsics": extrinsics,
        }

        return cls(**cam_dict)

    def save(self, path: str):
        save_yaml(Path(path), self.as_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "CameraCalibration":
        data = {k: v for k, v in data.items() if k != "header"}
        for k, v in data.items():
            if isinstance(v, list):
                data[k] = np.array(v)
        return cls(**data)

    @classmethod
    def load(cls, path: str):
        data = load_yaml(Path(path))
        header = data.get("header", {})
        if header.get("format") != cls.FORMAT:
            raise ValueError(
                f"Expected format '{cls.FORMAT}', got '{header.get('format')}'"
            )
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return (
            "CameraCalibration(\n"
            + f"  name='{self.name}',\n"
            + f"  model='{self.model}',\n"
            + f"  distortion_model='{self.distortion_model}',\n"
            + f"  intrinsics={self.intrinsics},\n"
            + f"  extrinsics={self.extrinsics},\n"
            + f"  distortion_coeffs={self.distortion_coeffs},\n"
            + f"  rectification={self.rectification},\n"
            + f"  rectified_projection={self.rectified_projection},\n"
            + f"  width={self.width},\n"
            + f"  height={self.height},\n"
            + ")"
        )


class StereoCalibration:
    """Stereo camera calibration holding a left (cam0) and right (cam1) CameraCalibration."""

    _SUPPORTED_DISTORTION_MODELS = {"RADTAN", "RATIONAL_POLYNOMIAL"}

    def __init__(self, cam0: CameraCalibration, cam1: CameraCalibration):
        self.cam0 = cam0  # left camera
        self.cam1 = cam1  # right camera
        self.maps: StereoRectification | None = None
        self.disparity_to_3d: Matrix4x4 | None = None

        if self.is_rectified:
            self.disparity_to_3d = self._compute_Q(cam0, cam1)
            self.maps = self._compute_maps(cam0, cam1)

    @property
    def is_rectified(self) -> bool:
        return (
            self.cam0.rectified_projection is not None
            and self.cam1.rectified_projection is not None
            and self.cam0.rectification is not None
            and self.cam1.rectification is not None
        )

    @staticmethod
    def _compute_maps(
        cam0: CameraCalibration, cam1: CameraCalibration
    ) -> StereoRectification:
        R0, R1 = cam0.R_rect, cam1.R_rect
        P0, P1 = cam0.P_rect, cam1.P_rect
        Q = StereoCalibration._compute_Q(cam0, cam1)

        map1_l, map2_l = cv2.initUndistortRectifyMap(
            cam0.K, np.array(cam0.d), R0, P0, cam0.res, cv2.CV_16SC2
        )
        map1_r, map2_r = cv2.initUndistortRectifyMap(
            cam1.K, np.array(cam1.d), R1, P1, cam1.res, cv2.CV_16SC2
        )
        return StereoRectification(
            map1_l=map1_l,
            map2_l=map2_l,
            map1_r=map1_r,
            map2_r=map2_r,
            R0=R0,
            R1=R1,
            P0=P0,
            P1=P1,
            Q=Q,
        )

    @staticmethod
    def _compute_Q(cam0: CameraCalibration, cam1: CameraCalibration) -> Matrix4x4:
        fx = cam0.rectified_projection[0]
        cx0 = cam0.rectified_projection[2]
        cy0 = cam0.rectified_projection[3]
        cx1 = cam1.rectified_projection[2]
        # rectified_projection[4] is P1[0,3] = Tx_meters * fx.
        # Q needs the raw baseline in meters.
        Tx = cam1.rectified_projection[4] / fx
        return np.array(
            [
                [1, 0, 0, -cx0],
                [0, 1, 0, -cy0],
                [0, 0, 0, fx],
                [0, 0, -1.0 / Tx, (cx0 - cx1) / Tx],
            ]
        )

    def rectify(self, force: bool = False) -> "StereoCalibration":
        """Compute stereo rectification and return a new StereoCalibration.

        If already rectified and force is False, returns self.

        The returned StereoCalibration has rectified CameraCalibrations
        (with rectification and rectified projection set) and stereo-level data
        (remap tables, Q matrix). Original intrinsics, extrinsics, and
        distortion are preserved.
        """
        if self.is_rectified and not force:
            return self

        cal0, cal1 = self.cam0, self.cam1

        supported = self._SUPPORTED_DISTORTION_MODELS
        if cal0.distortion_model.upper() not in supported:
            raise ValueError(
                f"Unsupported distortion model '{cal0.distortion_model}' on {cal0.name}. "
                f"Supported: {sorted(supported)}"
            )
        if cal0.distortion_model.upper() != cal1.distortion_model.upper():
            raise ValueError(
                f"Distortion model mismatch: {cal0.name}={cal0.distortion_model}, "
                f"{cal1.name}={cal1.distortion_model}"
            )

        K0 = cal0.K.astype(np.float64)
        K1 = cal1.K.astype(np.float64)
        D0 = np.array(cal0.d).astype(np.float64)
        D1 = np.array(cal1.d).astype(np.float64)

        # cv2.stereoRectify expects R and T that go from cam0 to cam1.
        # cal1.extrinsics_matrix is [R | t] where t is in the rotated frame,
        # so T in cam0's frame is R^T @ t.
        R = cal1.extrinsics_matrix[:3, :3].astype(np.float64)
        T = (R.T @ cal1.extrinsics_matrix[:3, 3]).astype(np.float64)

        R0, R1, P0, P1, Q, _, _ = cv2.stereoRectify(
            K0,
            D0,
            K1,
            D1,
            cal0.res,
            R,
            T.flatten(),
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0,
        )

        def _rectified_projection_from_matrix(P):
            return np.array([P[0, 0], P[1, 1], P[0, 2], P[1, 2], P[0, 3], P[1, 3]])

        rect_cam0 = CameraCalibration(
            intrinsics=cal0.intrinsics,
            extrinsics=cal0.extrinsics,
            distortion_coeffs=cal0.distortion_coeffs,
            model=cal0.model,
            distortion_model=cal0.distortion_model,
            width=cal0.width,
            height=cal0.height,
            name=cal0.name,
            rectification=Rot.from_matrix(R0).as_quat(),
            rectified_projection=_rectified_projection_from_matrix(P0),
            parent=cal0.parent,
        )
        rect_cam1 = CameraCalibration(
            intrinsics=cal1.intrinsics,
            extrinsics=cal1.extrinsics,
            distortion_coeffs=cal1.distortion_coeffs,
            model=cal1.model,
            distortion_model=cal1.distortion_model,
            width=cal1.width,
            height=cal1.height,
            name=cal1.name,
            rectification=Rot.from_matrix(R1).as_quat(),
            rectified_projection=_rectified_projection_from_matrix(P1),
            parent=cal1.parent,
        )

        return StereoCalibration(rect_cam0, rect_cam1)

    FORMAT = "psilia-stereo-calibration"

    def as_dict(self) -> dict:
        return {
            "header": {
                "format": self.FORMAT,
                "is_rectified": self.is_rectified,
                "resolution": [self.cam0.width, self.cam0.height],
            },
            "cam0": self.cam0.as_dict(include_header=False),
            "cam1": self.cam1.as_dict(include_header=False),
        }

    def save(self, path: str):
        save_yaml(Path(path), self.as_dict())

    @classmethod
    def load(cls, path: str, strict: bool = True) -> "StereoCalibration":
        data = load_yaml(Path(path))
        header = data.get("header", {})
        if header.get("format") == cls.FORMAT:
            cam0 = CameraCalibration.from_dict(data["cam0"])
            cam1 = CameraCalibration.from_dict(data["cam1"])
            return cls(cam0, cam1)
        if strict:
            raise ValueError(
                f"Expected format '{cls.FORMAT}', got '{header.get('format')}'"
            )
        try:
            return cls.from_kalibr(path)
        except Exception as e:
            raise ValueError(
                f"Could not load '{path}' as psilia or Kalibr calibration: {e}"
            ) from e

    @classmethod
    def from_kalibr(cls, yaml_path: str) -> "StereoCalibration":
        """Load a stereo pair from a Kalibr camchain YAML file."""
        cam0 = CameraCalibration.from_kalibr(yaml_path, "cam0")
        cam1 = CameraCalibration.from_kalibr(yaml_path, "cam1")
        return cls(cam0, cam1)

    def __str__(self) -> str:
        # TODO: Better formatting here please.
        s = "StereoCalibration:\n" + str(self.cam0) + "\n" + str(self.cam1)
        return s
