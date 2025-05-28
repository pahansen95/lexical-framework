#!/bin/bash
set -euo pipefail

VENV_DIR=".venv"

# Dependency checks
[[ $(git rev-parse --git-dir 2>/dev/null) ]] || { echo "Not in git repo"; exit 1; }
command -v pyenv >/dev/null || { echo "pyenv required"; exit 1; }
command -v uv >/dev/null || { echo "uv required"; exit 1; }

ROOT=$(git rev-parse --show-toplevel)
[[ -f "$ROOT/.python-version" ]] || { echo ".python-version file required"; exit 1; }

VERSION=$(cat "$ROOT/.python-version" | tr -d '[:space:]')
[[ -n "$VERSION" ]] || { echo ".python-version empty"; exit 1; }

# Install Python if needed
if ! pyenv versions --bare | grep -q "^$VERSION$"; then
    AVAILABLE=$(pyenv install --list | grep -E "^\s*$VERSION" | sed 's/^[[:space:]]*//' | grep -v '[a-zA-Z]' | sort -V | tail -1)
    [[ -n "$AVAILABLE" ]] || { echo "No Python version matching $VERSION"; exit 1; }
    pyenv install "$AVAILABLE"
    VERSION="$AVAILABLE"
fi

pyenv local "$VERSION"

# Setup venv
if [[ ! -d "$ROOT/$VENV_DIR" ]]; then
    cd "$ROOT"
    uv venv --python "$(pyenv which python)" "$VENV_DIR"
fi

# Install pre-dependencies
if [[ -f "$ROOT/pyproject.toml" ]]; then
    cd "$ROOT"
    source "$VENV_DIR/bin/activate"
    uv pip install -e .
fi

echo "Setup complete. Activate: source $VENV_DIR/bin/activate"