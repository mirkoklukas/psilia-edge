from collections import namedtuple
from typing import Any, TypeAlias

import cv2
import numpy as np
import yaml
from scipy.spatial.transform import Rotation as Rot

from .utils import load_yaml, save_yaml

Array: TypeAlias = Any

StereoRectification = namedtuple('StereoRectification', [
    'map1_l', 'map2_l', 'map1_r', 'map2_r',
    'R0', 'R1', 'P0', 'P1', 'Q',
])
Matrix: TypeAlias = Array
Matrix3x4: TypeAlias = Array



class CameraCalibration:
    """
    Camera Calibration.

    Note: This class roughly mimics the structure of the calibration output from kalibr.
    > https://github.com/ethz-asl/kalibr/wiki/yaml-formats
    """

    def __init__(
        self,
        intrinsics: Array,
        distortion_coeffs: Array,
        model: str = "PINHOLE",
        distortion_model: str = "RADTAN",
        width: int = -1,
        height: int = -1,
        name: str = "",
        # TODO: maybe rather *local* extrinsics (relative to the lead camera)??
        extrinsics: Array = None,
        parent: str|None = None
    ):
        """"
        Args:
            intrinsics: [fx, fy, cx, cy]
            distortion_coeffs: [k1, k2, p1, p2, k3] for RADTAN distortion model
            model: camera model, e.g. "PINHOLE"
            distortion_model: distortion model, e.g. "RADTAN"
            width: image width in pixels
            height: image height in pixels
            name: camera name (e.g. "cam0")
            extrinsics: [tx, ty, tz, qx, qy, qz, qw], if set, it describes
                a transformation from the parent frame (e.g. lead camera)
                to this camera, such that the camera projection is
                given by P = K @ [Q | t].
            parent: name of the parent frame (e.g. "cam0" for cam1 if cam0 is the lead camera)
        """
        self.intrinsics = intrinsics
        self.distortion_coeffs = distortion_coeffs
        self.model = model
        self.distortion_model = distortion_model
        self.width = width
        self.height = height
        self.name = name
        self.parent = parent

        extrinsics = extrinsics if extrinsics is not None else np.array([0.,0.,0.,0.,0.,0.,1.])
        x = extrinsics[:3]
        q = extrinsics[3:]

        # Mapping from ambient frame (lead camera) to camera frame (this camera), M = [R | t],
        # such that, the camera projection is given by P = K @ M.
        self.extrinsics = extrinsics
        self.extrinsics_matrix = np.concatenate([
                Rot.from_quat(q).as_matrix(),
                x[:, None]
            ], axis=-1)

        # Construct the intrinsics matrix K from the intrinsics vector.
        fx, fy, cx, cy = intrinsics
        self.intrinsics_matrix = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0,  0,  1]])

        self.camera_matrix = self.intrinsics_matrix @ self.extrinsics_matrix



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
        return self.camera_matrix

    @property
    def res(self):
        return (self.width, self.height)

    def rescale(self, factor: float) -> "CameraCalibration":
        """Return a new CameraCalibration with intrinsics and resolution scaled.

        Args:
            factor: Scale factor (e.g. 0.5 halves the resolution).

        Distortion coefficients and extrinsics are unchanged.
        """
        fx, fy, cx, cy = self.intrinsics
        return CameraCalibration(
            intrinsics=np.array([fx * factor, fy * factor, cx * factor, cy * factor]),
            distortion_coeffs=self.distortion_coeffs.copy(),
            model=self.model,
            distortion_model=self.distortion_model,
            width=int(self.width * factor),
            height=int(self.height * factor),
            name=self.name,
            extrinsics=self.extrinsics.copy(),
            parent=self.parent,
        )

    def as_dict(self):
        return {
            "intrinsics": self.intrinsics,
            "distortion_coeffs": self.distortion_coeffs,
            "model": self.model,
            "distortion_model": self.distortion_model,
            "width": self.width,
            "height": self.height,
            "name": self.name,
            "extrinsics": self.extrinsics
        }

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
            "extrinsics": extrinsics
        }

        return cls(**cam_dict)

    def save(self, path: str):
        save_yaml(path, self.as_dict())

    @classmethod
    def stereo_rectification(cls, cal0: "CameraCalibration", cal1: "CameraCalibration") -> StereoRectification:
        """Compute stereo rectification remap tables from two CameraCalibrations.

        Args:
            cal0: Left camera calibration (lead camera).
            cal1: Right camera calibration (must have extrinsics relative to cal0).

        Returns:
            StereoRectification namedtuple with remap tables (CV_16SC2) and
            rectification matrices R0, R1, P0, P1, Q.
        """
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
            K0, D0, K1, D1,
            cal0.res,
            R, T.flatten(),
            flags=cv2.CALIB_ZERO_DISPARITY, alpha=0,
        )

        # CV_16SC2: fixed-point with interpolation weights — fastest format for cv2.remap.
        map1_l, map2_l = cv2.initUndistortRectifyMap(K0, D0, R0, P0, cal0.res, cv2.CV_16SC2)
        map1_r, map2_r = cv2.initUndistortRectifyMap(K1, D1, R1, P1, cal1.res, cv2.CV_16SC2)

        return StereoRectification(
            map1_l=map1_l, map2_l=map2_l,
            map1_r=map1_r, map2_r=map2_r,
            R0=R0, R1=R1, P0=P0, P1=P1, Q=Q,
        )
