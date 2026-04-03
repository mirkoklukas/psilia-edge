# Inference

> What we compute and publish, what we need to do that, how we implement and wire it together.


## Image Stream

**What we need:**
- Stereo USB camera (single USB device, side-by-side left/right frame)
- `v4l2` access inside the Docker container
- Calibration file (path configured in `runtime.yaml`):
  - Two entries: `cam0` (left) and `cam1` (right)
  - Each entry contains intrinsics (focal length, principal point, distortion coefficients) and a 3D pose
  - `cam0` pose is identity (reference frame)
  - `cam1` pose is the transform from cam1 to cam0 (i.e. cam1 expressed in cam0's frame)
  - Format should be compatible with a `CameraInfo` class (TBD)

**What we publish:**
- `/psilia/image/raw` — raw side-by-side stereo frame
- `/psilia/image/left/raw` — left image, cropped from raw
- `/psilia/image/right/raw` — right image, cropped from raw
- `/psilia/image/left/rectified` — left image, undistorted and rectified
- `/psilia/image/right/rectified` — right image, undistorted and rectified
- `/psilia/image/left/camera_info` — K, D, R, P for left camera
- `/psilia/image/right/camera_info` — K, D, R, P for right camera

**Implementation:**
- TODO


## Depth Inference


## Pose Inference
