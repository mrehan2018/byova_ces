#!/usr/bin/env bash
# Install the Google CES (GECX) adapter into an existing BYOVA gateway (non-Docker Linux).
# It backs up every file it touches, installs the Python packages and copies the code.
# It does NOT edit config.yaml and does NOT restart the gateway - you do both (guide steps 6-7).
#
# Usage: ./tools/install.sh <gateway_dir> [python] [--force]
#   python  : the interpreter your gateway runs with (default: <gateway_dir>/venv/bin/python,
#             <gateway_dir>/.venv/bin/python, then python3)
#   --force : overwrite files that the compatibility check reports as CUSTOMIZED
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
FORCE=0; ARGS=()
for a in "$@"; do [ "$a" = "--force" ] && FORCE=1 || ARGS+=("$a"); done
GW="${ARGS[0]:-}"; PY="${ARGS[1]:-}"
[ -n "$GW" ] && [ -d "$GW" ] || { echo "Usage: $0 <gateway_dir> [python] [--force]"; exit 1; }
GW="$(cd "$GW" && pwd)"
if [ -z "$PY" ]; then
  for c in "$GW/venv/bin/python" "$GW/.venv/bin/python" "$(command -v python3)"; do
    [ -x "$c" ] && PY="$c" && break
  done
fi

FILES="src/core/wxcc_gateway_server.py src/core/virtual_agent_router.py src/core/health_service.py
src/connectors/i_vendor_connector.py src/connectors/gecx_connector.py
src/utils/audio_normalizer.py src/utils/silero_speech_boundary.py src/utils/telephony_audio.py"

echo "== 1/5 compatibility check"
set +e; bash "$PKG/tools/check_compat.sh" "$GW" "$PY"; rc=$?; set -e
if [ $rc -eq 1 ]; then echo "Stopped: compatibility check failed."; exit 1; fi
if [ $rc -eq 2 ] && [ $FORCE -ne 1 ]; then
  echo "Stopped: customized files found. Re-run with --force only after you have reviewed them."; exit 2
fi

TS="$(date +%Y%m%d-%H%M%S)"
BK="$GW/backups/pre-ces-$TS"
echo; echo "== 2/5 backup -> $BK"
mkdir -p "$BK"
: > "$BK/ADDED_FILES"
for f in $FILES; do
  if [ -f "$GW/$f" ]; then mkdir -p "$BK/$(dirname "$f")"; cp -p "$GW/$f" "$BK/$f"
  else echo "$f" >> "$BK/ADDED_FILES"; fi
done
[ -f "$GW/config/config.yaml" ] && mkdir -p "$BK/config" && cp -p "$GW/config/config.yaml" "$BK/config/config.yaml"
[ -f "$GW/main.py" ] && cp -p "$GW/main.py" "$BK/main.py"
"$PY" -m pip freeze > "$BK/pip-freeze-before.txt" 2>/dev/null || true
echo "backup done ($(find "$BK" -type f | wc -l) files)"

echo; echo "== 3/5 python packages (CPU-only PyTorch first, then requirements-ces.txt)"
"$PY" -m pip install --upgrade pip >/dev/null
if "$PY" -c "import torch, torchaudio" 2>/dev/null; then
  echo "torch $("$PY" -c 'import torch;print(torch.__version__)') already installed - keeping it"
else
  "$PY" -m pip install "torch>=2.5.1,<2.6" "torchaudio>=2.5.1,<2.6" --index-url https://download.pytorch.org/whl/cpu
fi
"$PY" -m pip install -r "$PKG/requirements-ces.txt"

echo; echo "== 4/5 copy code"
for f in $FILES; do
  mkdir -p "$GW/$(dirname "$f")"
  cp "$PKG/$f" "$GW/$f"
  echo "  installed $f"
done
find "$GW/src" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo; echo "== 5/5 smoke test"
( cd "$GW" && "$PY" "$PKG/tools/smoke_test.py" --gateway-dir "$GW" ) || {
  echo; echo "Smoke test reported problems (see above). Fix them before restarting the gateway."
  echo "To undo everything: $PKG/tools/rollback.sh $BK"; exit 3; }

cat <<EOF

Install finished. Backup: $BK
Next (install guide):
  step 6 - add the gecx_connector block to $GW/config/config.yaml (config/gecx_connector.snippet.yaml)
  step 7 - restart the gateway service, then re-run:  (cd $GW && $PY $PKG/tools/smoke_test.py --gateway-dir $GW)
Rollback at any time:  $PKG/tools/rollback.sh $BK
EOF
