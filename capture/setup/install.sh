#!/bin/sh
# One-shot Mac-side setup for Her_Proof. Safe to re-run.
#
# Before running:  full Xcode installed AND signed in to an Apple ID
#                  (Xcode > Settings > Accounts), iPhone plugged in over USB.
# Usage:           sh setup/install.sh            # then follow the printed next steps
set -eu
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1; }

step "Checking Xcode"
if ! need xcodebuild || ! xcodebuild -version >/dev/null 2>&1; then
  echo "Full Xcode is required (not just Command Line Tools). Install it from the App Store, open it once, then re-run." >&2; exit 1
fi
xcodebuild -version | head -1
if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "Apple Development"; then
  echo "No 'Apple Development' signing certificate. In Xcode: Settings > Accounts > sign in, select your team, then 'Manage Certificates' > + > Apple Development." >&2; exit 1
fi

step "Resolving Apple Team ID"
if [ -z "${WDA_TEAM_ID:-}" ]; then
  # The parenthesised code in the certificate name is NOT the team; the OU is.
  WDA_TEAM_ID=$(security find-certificate -c "Apple Development" -p 2>/dev/null | openssl x509 -noout -subject 2>/dev/null | sed -n 's/.*OU *= *\([A-Z0-9]\{10\}\).*/\1/p' | head -1)
fi
[ -n "$WDA_TEAM_ID" ] || { echo "Could not determine your Team ID. Export WDA_TEAM_ID=<10 chars> and re-run." >&2; exit 1; }
echo "Team ID: $WDA_TEAM_ID"

step "Homebrew + libimobiledevice + ffmpeg"
need brew || { echo "Install Homebrew first: https://brew.sh" >&2; exit 1; }
brew list libimobiledevice >/dev/null 2>&1 || brew install libimobiledevice
need ffmpeg || brew install ffmpeg

step "iphone-use daemon"
if [ ! -x "$HOME/Applications/iPhoneUse.app/Contents/MacOS/iphone-use-mcp" ]; then
  curl -fsSL https://raw.githubusercontent.com/leeguooooo/iphone-use/main/install.sh | sh
fi
sh setup/patch-setup-wda.sh

step "iOS platform for Xcode (needed to target a physical iPhone; one-time multi-GB download)"
if ! xcrun simctl runtime list 2>/dev/null | grep -q "iOS .*Ready"; then
  xcodebuild -downloadPlatform iOS
fi

step "iPhone over USB"
UDID=$(idevice_id -l 2>/dev/null | head -1 || true)
[ -n "$UDID" ] || { echo "No iPhone visible over USB. Plug it in, unlock it, tap 'Trust This Computer', then re-run." >&2; exit 1; }
echo "UDID: $UDID"
if idevicedevmodectl list 2>/dev/null | grep -q disabled; then
  idevicedevmodectl reveal >/dev/null 2>&1 || true
  echo "Developer Mode is off. On the iPhone: Settings > Privacy & Security > Developer Mode > on (it restarts). Then re-run." >&2; exit 1
fi

step "Project .env"
PW=$(plutil -extract EnvironmentVariables.PHONE_REMOTE_PASSWORD raw -o - "$HOME/Library/LaunchAgents/com.leeguoo.iphone-use.plist" 2>/dev/null || true)
if [ ! -f .env ]; then
  cat > .env <<ENV
PHONE_REMOTE_URL=http://127.0.0.1:44321
PHONE_REMOTE_TOKEN=$PW
PHONE_REMOTE_OWNER=herproof
WDA_TEAM_ID=$WDA_TEAM_ID
WDA_UDID=$UDID
PHONE_REMOTE_UDID=$UDID
# ANTHROPIC_API_KEY=sk-ant-...   (or run: ant auth login)
# GEMINI_API_KEY=...
# HERPROOF_PROVIDER=auto         (auto | claude | gemini)
ENV
  echo "wrote .env"
else
  echo ".env exists, leaving it"
fi

step "Register the iPhone in your developer account + first WebDriverAgent build"
# setup-wda.sh omits -allowProvisioningDeviceRegistration for Apple-ID logins, so do it once here.
WDA_DIR="$HOME/.iphone-use/WebDriverAgent"
if [ ! -d "$WDA_DIR" ]; then
  git clone -q https://github.com/appium/WebDriverAgent "$WDA_DIR"
fi
BUNDLE="com.leeguoo.iphone-use.wda.$(printf '%s' "$WDA_TEAM_ID" | tr 'A-Z' 'a-z')"
( cd "$WDA_DIR" && xcodebuild -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner \
    -destination "platform=iOS,id=$UDID" -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
    DEVELOPMENT_TEAM="$WDA_TEAM_ID" PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE" build-for-testing 2>&1 \
    | grep -E "error:|BUILD" | sort -u ) || true

step "Build, sign, install and supervise WebDriverAgent"
WDA_UDID="$UDID" WDA_TEAM_ID="$WDA_TEAM_ID" "$HOME/.iphone-use/setup-wda.sh"

step "Claude Code MCP registration (optional, for driving the phone interactively)"
if need claude; then
  claude mcp get iphone-use >/dev/null 2>&1 || claude mcp add iphone-use \
    -e PHONE_REMOTE_URL=http://127.0.0.1:44321 -e PHONE_REMOTE_TOKEN="$PW" \
    -- "$HOME/Applications/iPhoneUse.app/Contents/MacOS/iphone-use-mcp"
fi

step "Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

cat <<'DONE'

Done. Next:
  1. If the iPhone shows "Untrusted Developer": Settings > General > VPN & Device Management > trust the profile.
  2. Live view / recording: QuickTime Player > File > New Movie Recording > camera dropdown > your iPhone.
  3. Run an extraction (phone plugged in and unlocked):
       source .venv/bin/activate
       python -m herproof.extract --chat "Team 2"
  4. Give the phone back:   ~/.iphone-use/setup-wda.sh pause     (resume with: ... resume)
DONE
