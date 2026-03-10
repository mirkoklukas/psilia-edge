# Notes

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
