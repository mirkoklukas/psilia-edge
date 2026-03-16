# Notes

## Establishing a network connection to your Jetson

The simplest way to connect your MacBook and Jetson is to put both on the same network — either on the same Wi-Fi, or connected via an ethernet cable. Once on the same network, set up mDNS on the Jetson so you can reach it by name instead of IP.

> **mDNS** = Multicast DNS. Regular DNS uses a central server to resolve names to IPs. mDNS has no server — devices multicast directly on the LAN, announcing their own name and answering queries from others. On Linux this is handled by avahi-daemon, which reads the hostname from /etc/hostname and advertises it as hostname.local on all active interfaces, keeping it updated if IPs change.

Setup on Jetson:
```bash
# 1. set the hostname
sudo hostnamectl set-hostname jetson

#2. install and enable avahi
sudo apt update
sudo apt install avahi-daemon
sudo systemctl enable --now avahi-daemon

# 3. verify
avahi-resolve -n jetson.local
```

Then from your MacBook:
```bash
# verify connection
ping jetson.local

# SSH into the Jetson
ssh user@jetson.local
```

This works without knowing or setting any IP addresses. If the Jetson's IP changes, jetson.local still resolves correctly.

## Development

### Local environment variables (direnv)

The runtime uses environment variables to override Jetson-specific default paths. When
developing or testing on a laptop, override them to local paths using
[direnv](https://direnv.net/).

**Install:**
```bash
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc
```

**Add to `.gitignore`**
```bash
# Local env vars, e.g. for development
# and testing directory for the runtime host
.envrc
_dev/
```

```bash
# From the root of the psilia-edge repo
mkdir -p ./_dev
python scripts/bootstrap.py _dev --system-dir _dev/system --no-setup
```
**Create `.envrc` in the project root:**
```bash
export PSILIA_CONFIG_DIR=$PWD/_dev/system/config
export PSILIA_RUN_DIR=$PWD/_dev/system/run
export PSILIA_LOG_DIR=$PWD/_dev/system/log
export PSILIA_BASE_DIR=$PWD/_dev/psilia
```

Then allow it once: `direnv allow`

The vars are loaded automatically when you `cd` into the project and unloaded when you leave.
`.envrc` is gitignored.
