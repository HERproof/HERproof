#!/bin/sh
# Save a phone screenshot to evidence/screens/<date>_<NN>_<name>.png
set -eu
cd "$(dirname "$0")/.."
. ./.env
name="${1:-shot}"; d=$(date +%Y-%m-%d); mkdir -p evidence/screens
n=$(ls evidence/screens/${d}_*.png 2>/dev/null | wc -l | tr -d ' ')
out=$(printf 'evidence/screens/%s_%02d_%s.png' "$d" "$n" "$name")
curl -s -m 20 -H "Authorization: Bearer $PHONE_REMOTE_TOKEN" "$PHONE_REMOTE_URL/agent/screenshot" -o "$out"
echo "$out"
