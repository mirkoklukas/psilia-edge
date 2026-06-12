#!/bin/bash
# Best to run this script via `source init.sh`
WORKSPACE="$HOME/workspace"

# # # # # # # # # # # # #
#   Add to .bashrc
# # # # # # # # # # # # #
BASHRC_SECTION_START="# >>> PSILIA-LAMBDA INIT >>>"
BASHRC_SECTION_END="# <<< PSILIA-LAMBDA INIT <<<"

# Remove old section if it exists
if grep -q "$BASHRC_SECTION_START" ~/.bashrc; then
    # Remove the section (inclusive between the section markers)
    sed -i "/$BASHRC_SECTION_START/,/$BASHRC_SECTION_END/d" ~/.bashrc
fi

# Add new section
{
    echo "$BASHRC_SECTION_START"
    echo "export WORKSPACE=\"$WORKSPACE\""
    echo "alias hs='cd \"\$WORKSPACE\"'"
    echo "source \$WORKSPACE/psilia-core/.venv/bin/activate"
    echo "$BASHRC_SECTION_END"
} >> ~/.bashrc
source ~/.bashrc

# # # # # # # # # # # # #
#   Store git credentials in storage
# # # # # # # # # # # # #
git config --global credential.helper "store --file \"$WORKSPACE/.git-credentials\""
# After your first `git pull` or `git clone` command
# your username and password token will be saved in $WORKSPACE/.git-credentials
# and will be used automatically for future git operations.

# # # # # # # # # # # # #
#   Install UV
# # # # # # # # # # # # #
# > https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh
