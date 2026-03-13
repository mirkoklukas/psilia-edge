#!/bin/bash
#
#   This just sources the environment and then executes
#   the command passed as arguments to this script.
#
set -e

for f in /etc/profile.d/*.sh; do
    [ -r "$f" ] && source "$f"
done

exec "$@"
