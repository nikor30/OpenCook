#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -e "core[dev]"

# `miiocli genericmiot` only exists on python-miio master (0.6 dev), not in the 0.5.x releases.
pip install "python-miio @ git+https://github.com/rytilahti/python-miio.git@9a00e0888ef85f8d8d84888cabd9e46d1b0a18df"

# Isolated from the project env: mitmproxy pins many dependencies.
pipx install mitmproxy

pre-commit install
