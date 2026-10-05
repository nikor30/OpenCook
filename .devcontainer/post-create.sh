#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -e "core[dev]"

# Isolated from the project env: mitmproxy pins many dependencies.
pipx install mitmproxy

pre-commit install
