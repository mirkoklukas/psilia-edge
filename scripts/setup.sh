#!/usr/bin/env bash
# Psilia Edge — Setup
#
# Run from the directory where you want psilia installed:
#
#   cd /ssd
#   curl -fsSL https://raw.githubusercontent.com/mirkoklukas/psilia-edge/main/scripts/setup.sh | bash
#
# Or with a custom install directory:
#
#   curl -fsSL .../setup.sh | bash -s -- --install-dir /data/psilia

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

ok()   { echo "  ✓ $1"; }
info() { echo "  $1"; }
fail() { echo "  ✗ $1" >&2; exit 1; }

# ── preflight ─────────────────────────────────────────────────────────────────

echo ""
echo "Psilia Edge — Setup"
echo "Install directory: $INSTALL_DIR"
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

# ── /opt/psilia (requires sudo) ───────────────────────────────────────────────

info "Creating /opt/psilia/ (requires sudo)…"
sudo mkdir -p /opt/psilia
if [ ! -f /opt/psilia/runtime_config.yaml ]; then
    sudo touch /opt/psilia/runtime_config.yaml
fi
ok "/opt/psilia/runtime_config.yaml ready"

# ── run setup wizard ──────────────────────────────────────────────────────────

echo ""
echo "Bootstrap complete. Starting setup wizard…"
echo ""

python -m psilia_edge.runtime.setup --install-dir "$INSTALL_DIR"
