#!/bin/sh
# iphone-use's setup-wda.sh aborts on Macs that have never configured a system
# proxy: its parser requires HTTPEnable/HTTPSEnable/SOCKSEnable keys that
# `scutil --proxy` omits in that case. The launchd supervisor re-runs the script
# without any env vars, so an environment workaround is not enough. This makes
# a missing key count as "no proxy". Re-run after every iphone-use reinstall.
set -eu
f="$HOME/.iphone-use/setup-wda.sh"
[ -f "$f" ] || { echo "not installed: $f" >&2; exit 1; }
if grep -q 'if (!root_seen || depth != 0 || invalid) {' "$f"; then
  echo "already patched: $f"; exit 0
fi
cp "$f" "$f.orig"
sed -i '' 's/if (!root_seen || !enable_seen || depth != 0 || invalid) {/if (!root_seen || depth != 0 || invalid) {/' "$f"
grep -q 'if (!root_seen || depth != 0 || invalid) {' "$f" && echo "patched: $f (original at $f.orig)"
