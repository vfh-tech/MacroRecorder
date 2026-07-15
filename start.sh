#!/bin/bash
# Mengambil direktori tempat script ini berada
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
    python -m macrorecorder
else
    echo "Error: Virtual environment (.venv) tidak ditemukan di $SCRIPT_DIR"
    exit 1
fi
