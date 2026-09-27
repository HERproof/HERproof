#!/bin/sh
# Record the phone screen while the agent works, from the WebDriverAgent MJPEG
# stream the daemon relays on port 9100. Output goes to evidence/recordings/.
# Usage: scripts/record.sh [label]      Stop with Ctrl-C.
set -eu
cd "$(dirname "$0")/.."
label="${1:-run}"
mkdir -p evidence/recordings
out="evidence/recordings/$(date +%Y-%m-%d_%H-%M-%S)_${label}.mp4"
echo "Recording to $out (Ctrl-C to stop)"
exec ffmpeg -loglevel warning -f mjpeg -i http://127.0.0.1:9100 \
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -r 10 -c:v libx264 -pix_fmt yuv420p "$out"
