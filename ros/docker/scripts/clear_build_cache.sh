#!/bin/bash
set -e

# Clear colcon build cache so any setup.py changes are picked up.
# Dirs are owned by root (created inside Docker), so we clear them by running
# a temporary container — no sudo needed on the host.
#
# NOTE: Probably cleaner long-term, pass --user uid:gid to docker run so build
# artifacts are owned by the calling user and can be deleted directly. Requires
# setting HOME=/tmp inside the container since the UID has no /etc/passwd entry.
for d in /psilia/ros/build /psilia/ros/install /psilia/ros/log; do
    [ -d "$d" ] && rm -rf "$d"
done
