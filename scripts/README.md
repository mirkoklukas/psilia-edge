# Kalibr

## Run Kalibr

Create a dataset folder with the structure below. The `<mcap_folder>` should contain a single `<mcap_file>.mcap` file, and optionally an `april_tags.yaml` file. If there is no `april_tags.yaml` file, the script will look for one in the parent folder.

```text
anywhere/
    april_tags.yaml (optional: needed if there is no `{mcap_folder}/april_tags.yaml`)
    {mcap_folder}/
        {my_mcap_file}.mcap
        april_tags.yaml (optional, either here or in the parent folder)
```

The `april_tags.yaml` file should have the following structure:

```yaml
target_type: "aprilgrid"
tagCols: 11 #| Number of april tags
tagRows: 8 #| Number of april tags
tagSize: 0.025 #| Size of april tag, edge to edge [m]
tagSpacing:
  0.28 #| Ratio of space between tags to tagSize, i.e.
  #| `tagSpacing = spaceBetweenTags / tagSize`
  #| Example: tagSize=0.025, spacing=0.007 => tagSpacing=0.28
```

Run the script with the **mcap folder** as an argument. It will assume a **april_tags.yaml** file
is in the _same_ folder or in the _parent_ folder, with the former taking priority. Results will be saved in a new sub-folder called `results{i}`.

```bash
# Build the docker images if not already built
docker build -t humble -f docker/Dockerfile.humble .
docker build -t kalibr -f docker/Dockerfile.kalibr .

# Run the script
./kalibr_rs_camera.sh <mcap_folder>
```

## Results

Results will be saved in a new sub-folder called `results{i}`.

- **calibration-camchain.yaml**: Contains the camera calibration results, and can be loaded using `CameraIntrinsics.from_kalibr_yaml(path)`.
- **calibration-poses-cam0.csv**: Contains the camera poses relative to the april targets. Or, put differently the transformation from camera coordinates to april tag coordinates. The pose/transform is stored as `x, q_inv`. The **header is WRONG**, the quaternion is stored as `x, y, z, w` (instead of `w, x, y, z` as indicated in the header).

### Note on camera models

We're running kalibr's **multi camera calibration** with a single camera.

```bash
rosrun kalibr kalibr_calibrate_cameras \
    --bag ./calibration.bag \
    --target ./april_tags.yaml \
    --models pinhole-radtan \
    --topics /sensor/camera/front/image_raw/compressed \
    --bag-freq 10 \
    --export-poses \
    --dont-show-report
```

**Alternatively** we can run kalibr's **rolling shutter camera calibration**. The command for that is as follows

```bash
rosrun kalibr kalibr_calibrate_rs_cameras \
    --bag ./calibration.bag \
    --target ./april_tags.yaml \
    --model pinhole-radtan-rs \
    --topic /sensor/camera/front/image_raw/compressed \
    --inverse-feature-variance 1 \
    --frame-rate 30 \
    --bag-freq 10
```


# TMUX

```bash
$ tmux new
$ tmux new -s session_name
$ tmux list-sessions
$ tmux ls
$ tmux attach -t session_name_or_number
$ tmux kill-session -t session_name_or_number
$ tmux kill-server
```
