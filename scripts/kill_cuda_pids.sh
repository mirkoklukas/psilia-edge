#!/bin/bash

# Get all PIDs using NVIDIA GPUs
pids=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
echo "Found PIDs using NVIDIA GPUs: ..."
echo $pids
# Kill each PID
for pid in $pids; do
    if [[ $pid =~ ^[0-9]+$ ]]; then
        kill -9 "$pid" && echo "Killed PID $pid"
    fi
done
