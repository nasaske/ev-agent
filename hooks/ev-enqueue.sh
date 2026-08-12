#!/usr/bin/env bash
set -euo pipefail

PAYLOAD=$(cat)

TRANSCRIPT=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
print(payload.get("transcript_path", ""))
' 2>/dev/null || true)

[ -z "$TRANSCRIPT" ] && exit 0
[ -f "$TRANSCRIPT" ] || exit 0

if command -v ev >/dev/null 2>&1; then
    ev enqueue --quiet "$TRANSCRIPT" >/dev/null 2>&1 || true
else
    python3 -m ev_agent enqueue --quiet "$TRANSCRIPT" >/dev/null 2>&1 || true
fi

exit 0
