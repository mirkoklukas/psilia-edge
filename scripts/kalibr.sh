#!/bin/bash
# shellcheck disable=SC1234,SC2086

# Check if all required arguments are provided
# and read them into variables
if [ $# -ne 4 ]; then
    echo "Usage: $0 <rosbag_folder> <topic_string> <april_tags_file> <results_folder>"
    exit 1
fi
rosbag=$(realpath "$1")
topic=$2
april_tags=$(realpath "$3")
results=$(realpath "$4")

# Get the file format from the rosbag folder
# by checking if .db3 or .mcap exists
format=""
if [ -f "$rosbag"/*.db3 ]; then
    format="sqlite3"
elif [ -f "$rosbag"/*.mcap ]; then
    format="mcap"
else
    echo "Error: Could not determine rosbag format." \
         "Expected .db3 or .mcap file alongside metadata.yaml"
    exit 1
fi

echo "Running kalibr script"
echo "rosbag: $rosbag ($format)"
echo "topic: $topic"
echo "april_tags: $april_tags"
echo "results: $results"

# Convert ROS2 rosbag to ROS1 bag format
# > https://github.com/ethz-asl/kalibr/wiki/ROS2-Calibration-Using-Kalibr
docker run --rm -it --name humble -v $rosbag:/stage/rosbag humble bash -c "\
    cd /stage/rosbag && \
    ls -la && \
    ros2 bag reindex -s $format ./ && \
    rosbags-convert --src ./ --dst ./calibration.bag --src-typestore ros2_humble"

# Move the converted rosbag and april tags
# file to the results folder
mv $rosbag/calibration.bag $results/
cp $april_tags $results

# Run kalibr script
docker run --rm -it --name kalibr \
            -v $results:/stage/kalibr \
            kalibr bash -c "\
            cd /stage/kalibr && \
            rosrun kalibr kalibr_calibrate_cameras \
                --bag ./calibration.bag \
                --target ./april_tags.yaml \
                --models pinhole-radtan \
                --topics $topic \
                --bag-freq 10 \
                --export-poses \
                --dont-show-report"
