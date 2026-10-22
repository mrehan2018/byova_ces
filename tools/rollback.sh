#!/usr/bin/env bash
# Restore a BYOVA gateway to its state before tools/install.sh ran.
# Usage: ./tools/rollback.sh <backup_dir> [--restore-packages <python>]
#   e.g. ./tools/rollback.sh /opt/byova-gateway/backups/pre-ces-20261021-101500
# Restores code files, config.yaml and main.py, and removes files the install added.
# --restore-packages <python> also reinstalls the exact Python package versions that were
# installed before (pip-freeze-before.txt). Without it the new packages stay (harmless).
# Restart the gateway service afterwards.
set -euo pipefail
BK="${1:-}"
[ -n "$BK" ] && [ -f "$BK/ADDED_FILES" ] || { echo "Usage: $0 <backup_dir> [--restore-packages <python>]  (folder created by install.sh, contains ADDED_FILES)"; exit 1; }
BK="$(cd "$BK" && pwd)"
GW="$(cd "$BK/../.." && pwd)"
RESTORE_PY=""
[ "${2:-}" = "--restore-packages" ] && RESTORE_PY="${3:-python3}"
echo "Restoring $GW from $BK"
( cd "$BK" && find . -type f ! -name ADDED_FILES ! -name 'pip-freeze-before.txt' | sed 's|^\./||' ) | while read -r f; do
  mkdir -p "$GW/$(dirname "$f")"; cp -p "$BK/$f" "$GW/$f"; echo "  restored $f"
done
while read -r f; do
  [ -n "$f" ] && [ -f "$GW/$f" ] && rm -f "$GW/$f" && echo "  removed  $f"
done < "$BK/ADDED_FILES"
find "$GW/src" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
if [ -n "$RESTORE_PY" ]; then
  if [ -s "$BK/pip-freeze-before.txt" ]; then
    echo "Reinstalling the package versions from before the install ($BK/pip-freeze-before.txt)"
    "$RESTORE_PY" -m pip install -r "$BK/pip-freeze-before.txt"
  else
    echo "WARN: $BK/pip-freeze-before.txt is missing or empty - packages left as they are"
  fi
fi
echo "Rollback complete - now restart the gateway service (e.g. sudo systemctl restart <your-byova-service>)."
