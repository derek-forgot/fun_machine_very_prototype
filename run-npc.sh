#!/bin/bash
# One-click launcher (Linux, and macOS via "Run NPC.command"): Run NPC
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info[0] < 3)' 2>/dev/null; then
    exec "$py" launch.py app
  fi
done
echo
echo "Python 3 was not found. Install it from https://www.python.org/downloads/"
echo "(Linux: e.g. sudo apt install python3 python3-tk), then run this again."
echo
read -r -p "Press Enter to close..." _
exit 1
