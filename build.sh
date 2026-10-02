#!/usr/bin/env bash
set -euo pipefail
# Build single-file binary on Linux.
uv run pyinstaller --onefile --noconsole --name cuenta-paginas-pdf main.py
