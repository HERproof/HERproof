#!/bin/sh
# Reveal iMessage per-message times (slow drag left) and capture frames from
# the phone video stream mid-gesture. Keeps the best frame as
# evidence/screens/<date>_<NN>_<name>.png and all frames beside it as .jpg
# in evidence/screens/frames/<name>/ for review.
# Usage: scripts/times_snap.sh <name> [owner]   owner = MCP owner id, e.g. mcp-88749
set -eu
cd "$(dirname "$0")/.."
. ./.env
name="${1:-times}"; owner="${2:-${PHONE_REMOTE_OWNER:-}}"
d=$(date +%Y-%m-%d); mkdir -p evidence/screens "evidence/screens/frames/$name"
fd="evidence/screens/frames/$name"; rm -f "$fd"/f_*.jpg
ffmpeg -loglevel error -y -f mjpeg -i http://127.0.0.1:9100 -t 5 -vf fps=8 -q:v 2 "$fd/f_%02d.jpg" &
FF=$!
sleep 1.5
curl -s -m 15 -H "Authorization: Bearer $PHONE_REMOTE_TOKEN" -H "X-Phone-Control: 1" \
  ${owner:+-H "X-Phone-Owner: $owner"} -X POST "$PHONE_REMOTE_URL/agent/input" \
  -d '{"type":"drag","x1":0.85,"y1":0.5,"x2":0.35,"y2":0.5,"hold_ms":150,"duration_ms":2500}' >/dev/null
wait $FF
# the reveal is brief: keep the frame that differs most from the resting screen
best=$(python3 scripts/pick_frame.py "$fd")
n=$(ls evidence/screens/${d}_*.png 2>/dev/null | wc -l | tr -d ' ')
out=$(printf 'evidence/screens/%s_%02d_%s.png' "$d" "$n" "$name")
ffmpeg -loglevel error -y -i "$best" "$out"
echo "$out"
