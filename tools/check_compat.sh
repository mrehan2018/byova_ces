#!/usr/bin/env bash
# Read-only pre-check: is this BYOVA gateway safe to upgrade with the CES adapter files?
# Usage: ./tools/check_compat.sh <gateway_dir> [python]
# Exit code: 0 = safe to copy files as-is, 2 = customized files found (review first), 1 = error.
set -u
PKG="$(cd "$(dirname "$0")/.." && pwd)"
GW="${1:-}"
[ -n "$GW" ] && [ -d "$GW" ] || { echo "Usage: $0 <gateway_dir> [python]"; exit 1; }
GW="$(cd "$GW" && pwd)"
PY="${2:-}"
if [ -z "$PY" ]; then
  for c in "$GW/venv/bin/python" "$GW/.venv/bin/python" "$(command -v python3)"; do
    [ -x "$c" ] && PY="$c" && break
  done
fi

echo "== BYOVA CES adapter - compatibility check"
echo "gateway dir : $GW"
[ -f "$GW/main.py" ] && [ -f "$GW/src/core/wxcc_gateway_server.py" ] \
  || { echo "ERROR: $GW does not look like a BYOVA gateway (main.py / src/core/wxcc_gateway_server.py missing)"; exit 1; }
[ -f "$GW/src/generated/voicevirtualagent_pb2.py" ] \
  || echo "WARN : src/generated/voicevirtualagent_pb2.py not found - gRPC stubs must exist before starting"

echo "python      : $PY ($("$PY" --version 2>&1))"
"$PY" - <<'EOF'
import sys
v = sys.version_info
if v < (3, 9):
    print("ERROR: Python 3.9+ required"); sys.exit(1)
if v >= (3, 13):
    print("NOTE : Python 3.13+ -> requirements-ces.txt installs audioop-lts; PyTorch 2.5 wheels for 3.13 are limited, 3.10-3.12 recommended")
EOF

status=0
echo
echo "-- existing files that will be replaced"
for f in src/core/wxcc_gateway_server.py src/core/virtual_agent_router.py src/core/health_service.py src/connectors/i_vendor_connector.py; do
  ref="$PKG/reference/cisco-0f63e16/$f"
  cur_ref="$PKG/reference/cisco-current/$f"
  new="$PKG/$f"
  cur="$GW/$f"
  if [ ! -f "$cur" ]; then
    echo "  MISSING     $f (will be added)"
  elif diff -q -w "$ref" "$cur" >/dev/null 2>&1; then
    echo "  OK          $f (unchanged Cisco original - safe to replace)"
  elif diff -q -w "$cur_ref" "$cur" >/dev/null 2>&1; then
    echo "  OK          $f (unchanged Cisco current release - safe to replace)"
  elif diff -q -w "$new" "$cur" >/dev/null 2>&1; then
    echo "  OK          $f (already the CES adapter version)"
  else
    echo "  CUSTOMIZED  $f  -> differs from the Cisco original; see 'diff -u $ref $cur'"
    status=2
  fi
done

echo
echo "-- new files that will be added"
for f in src/connectors/gecx_connector.py src/utils/audio_normalizer.py src/utils/silero_speech_boundary.py src/utils/telephony_audio.py; do
  if [ ! -f "$GW/$f" ]; then echo "  NEW         $f"
  elif diff -q -w "$PKG/$f" "$GW/$f" >/dev/null 2>&1; then echo "  OK          $f (already present, identical)"
  else echo "  EXISTS      $f (different version - will be replaced; it is backed up first)"
  fi
done

echo
echo "-- connectors currently configured (must keep working)"
if [ -f "$GW/config/config.yaml" ]; then
  "$PY" - "$GW/config/config.yaml" <<'EOF' || true
import sys
try:
    import yaml
except ImportError:
    print("  (PyYAML not importable with this python - skipped)"); sys.exit(0)
cfg = yaml.safe_load(open(sys.argv[1])) or {}
for name, c in (cfg.get("connectors") or {}).items():
    c = c or {}
    agents = (c.get("config") or {}).get("agents")
    print(f"  {name:28s} class={c.get('class')} module={c.get('module')} agents={agents}")
print("  gecx_connector already configured" if "gecx_connector" in (cfg.get("connectors") or {}) else "  gecx_connector not configured yet (add it in step 6)")
EOF
else
  echo "  config/config.yaml not found"
fi

echo
echo "-- custom connectors that call the base class (review if CUSTOMIZED above)"
grep -l "IVendorConnector" "$GW"/src/connectors/*.py 2>/dev/null | grep -v -e i_vendor_connector.py -e gecx_connector.py | sed 's/^/  /'

echo
if [ $status -eq 0 ]; then
  echo "RESULT: OK - files can be copied as-is (run tools/install.sh)."
else
  echo "RESULT: CUSTOMIZED FILES FOUND - your gateway has local changes in the files above."
  echo "        Review the diffs, then either re-apply your changes on top of the new files,"
  echo "        or merge patches/*.patch into your files (see install guide, section 'Customized gateways')."
  echo "        install.sh will refuse to overwrite them unless run with --force."
fi
exit $status
