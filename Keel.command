#!/bin/bash
#  Double-click to open Keel on macOS. First run installs it.
cd "$(dirname "$0")" || exit 1

if ! python3 -c "import keel" >/dev/null 2>&1; then
  echo "First run - installing Keel..."
  python3 -m pip install -e ".[desktop]" || { echo "Install failed. Need Python 3.11+."; read -r; exit 1; }
fi

python3 -m keel app --dir data
