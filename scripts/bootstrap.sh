#!/usr/bin/env bash
# Psilia Edge — Bootstrap
#
# Run from the directory where you want psilia installed:
#
#   cd /ssd
#   curl -fsSL https://raw.githubusercontent.com/mirkoklukas/psilia-edge/main/scripts/bootstrap.sh | bash
#
# Or with a custom install directory:
#
#   curl -fsSL .../bootstrap.sh | bash -s -- --install-dir /data/psilia

set -e

REPO_URL="https://github.com/mirkoklukas/psilia-edge.git"
REPO_BRANCH="main"
INSTALL_DIR="$(pwd)/psilia"

# ── parse args ────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

REPO_DIR="$INSTALL_DIR/psilia-edge"

# ── helpers ───────────────────────────────────────────────────────────────────
HEADER=$(cat <<EOF
    ▄
  ▚ █ ▞   Psilia Edge → Bootstrap
    █     Install directory: $INSTALL_DIR
    ▀
EOF
)
header() { echo "$HEADER"; }
title() { echo "$1 → $2"; }
ok()   { echo "✓ $1"; }
info() { echo "$1"; }
fail() { echo "✗ $1" >&2; exit 1; }

# ── preflight ─────────────────────────────────────────────────────────────────
echo ""
header
echo ""


command -v git  >/dev/null 2>&1 || fail "git not found — install git and retry."
command -v pip  >/dev/null 2>&1 || fail "pip not found — install Python and retry."
command -v sudo >/dev/null 2>&1 || fail "sudo not found."

# ── directory structure ───────────────────────────────────────────────────────

info "Creating directory structure…"
mkdir -p "$INSTALL_DIR/psilia-edge"
mkdir -p "$INSTALL_DIR/ros/src"
mkdir -p "$INSTALL_DIR/data/recordings"
ok "Directories ready"

# ── clone or pull repo ────────────────────────────────────────────────────────

if [ -d "$REPO_DIR/.git" ]; then
    info "Repository already exists — pulling latest…"
    git -C "$REPO_DIR" pull
    ok "Repository updated"
else
    info "Cloning psilia-edge ($REPO_BRANCH)…"
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
    ok "Repository cloned to $REPO_DIR"
fi

# ── install psilia-edge ───────────────────────────────────────────────────────

info "Installing psilia-edge…"
pip install -e "$REPO_DIR" --quiet
ok "psilia-edge installed — 'psilia' command now available"

# ── copy psilia_runtime into ROS workspace ────────────────────────────────────

info "Copying psilia_runtime into ROS workspace…"
cp -r "$REPO_DIR/ros/psilia_runtime" "$INSTALL_DIR/ros/src/psilia_runtime"
ok "psilia_runtime ready at $INSTALL_DIR/ros/src/psilia_runtime"

# ── /opt/psilia (requires sudo) ───────────────────────────────────────────────

info "Creating /opt/psilia/ and writing runtime config (requires sudo)…"
sudo mkdir -p /opt/psilia
sudo tee /opt/psilia/runtime_config.yaml > /dev/null <<EOF
storage:
  base: $INSTALL_DIR
  data_path: $INSTALL_DIR/data
runtime:
  ros_workspace: $INSTALL_DIR/ros
EOF
ok "/opt/psilia/runtime_config.yaml written"

# ── run setup wizard ──────────────────────────────────────────────────────────

echo ""
echo "Bootstrap complete. Starting setup wizard…"
echo ""

psilia runtime setup
