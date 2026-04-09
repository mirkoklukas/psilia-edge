# Inference

> What we compute and publish, what we need to do that, how we implement and wire it together.


## Topic Interface

Stereo pipeline:
| Topic | Type | Description |
|---|---|---|
| `/psilia/stereo/image_raw` | `Image` (bgr8) | Raw side-by-side stereo frame |
| `/psilia/stereo/image_rect` | `Image` (bgr8) | Rectified side-by-side stereo frame |
| `/psilia/stereo/left/camera_info` | `CameraInfo` | Raw left camera intrinsics |
| `/psilia/stereo/right/camera_info` | `CameraInfo` | Raw right camera intrinsics |
| `/psilia/stereo/depth` | `Image` (32FC1) | Depth map in meters (0 = invalid) |
| `/psilia/stereo/depth/camera_info` | `CameraInfo` | Rectified left camera intrinsics (depth viewpoint) |

Preview (low-res, rate-limited for monitoring):
| Topic | Type | Description |
|---|---|---|
| `/psilia/preview/image/compressed` | `CompressedImage` | Downsampled raw stereo JPEG |
| `/psilia/preview/depth/compressed` | `CompressedImage` | Depth colormap (plasma, white=invalid) JPEG |
| `/psilia/preview/rectified/compressed` | `CompressedImage` | Downsampled rectified stereo JPEG |
| `/psilia/preview/pointcloud` | `PointCloud2` | Subsampled 3D point cloud |

Two pipeline paths exist — **GPU** (`depth_cuda_node`: raw → rectify → depth in one node) and **CPU** (`rectify_node` + `depth_node`). Both produce the same topic interface.


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

**Implementation:**
- TODO


## Depth Inference


## Pose Inference
