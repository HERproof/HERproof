# Her_Proof — setup notes from the first machine (Bhavya's Mac, 2026-09-25)

For a fresh machine use `README.md` and `sh setup/install.sh`; this file is the
history of what was done by hand here and why.


Goal: drive an iPhone over USB from Claude Code, open Messages, walk recent
chats, and save screenshots of messages that show bullying/harassment into
`evidence/` with a log of where each one came from.

Architecture:

    Claude Code  --MCP-->  iphone-use daemon (Mac, :44321)  --WDA/USB-->  iPhone

## Done on this Mac (2026-09-25)

- Xcode 26.1.1 with Apple Development signing identity (Team ID 3N74PKJ4AX)
- `brew install libimobiledevice` (gives `iproxy`, `idevice_id`)
- iphone-use v0.6.6 installed to `~/Applications/iPhoneUse.app`,
  daemon LaunchAgent `gui/501/com.leeguoo.iphone-use` running on port 44321
- MCP server `iphone-use` registered with Claude Code for this project
  (`claude mcp list`); token lives in `.env` and in the LaunchAgent plist
- Patched `~/.iphone-use/setup-wda.sh` (original kept as `.orig`): its proxy
  check aborted on Macs that never configured a system proxy. One-line awk
  fix so a missing `HTTPEnable` key counts as "no proxy". If iphone-use is
  ever reinstalled, re-apply that patch or WDA's supervisor will loop.
- Phone "Ava" (iPhone 17, iOS 26.6.2) registered in the developer account;
  WebDriverAgent built, installed, launched, supervised by launchd
  `gui/501/com.leeguoo.iphone-use.wda`. Daemon reports drivable=true.

## Re-run after a reboot, cable swap, or if `setup-wda.sh status` complains

1. Plug the iPhone in over USB. On the phone: Settings > Privacy & Security >
   Developer Mode > on (reboots), then tap "Trust This Computer". Keep the
   phone unlocked and awake the whole time.
2. Confirm the Mac sees it:

       idevice_id -l

3. Build, sign, install and launch WebDriverAgent (first run takes a few
   minutes; Xcode may prompt to trust the developer profile on the phone):

       set -a; source .env; set +a
       ~/.iphone-use/setup-wda.sh

       ~/.iphone-use/setup-wda.sh status

   If the phone says "Untrusted Developer", go to Settings > General >
   VPN & Device Management and trust the Apple Development profile.
4. Sanity check without AI: open http://127.0.0.1:44321/phone in a browser
   (password = PHONE_REMOTE_TOKEN in .env) and confirm you can see and tap
   the screen.
5. Restart Claude Code in this folder so the `iphone-use` MCP tools load,
   then test in order:
   - "Take a screenshot of my iPhone and describe what is on screen."
   - "Open Messages."
   - "Open the most recent conversation and scroll up once."
   Only after those work, run the evidence pass.

## Recording the run

Option A (simplest, most faithful): QuickTime Player > File > New Movie
Recording, click the arrow next to the record button, pick the iPhone as
camera. Records the real screen over USB, independent of the agent.

Option B: `scripts/record.sh <label>` saves the agent-side MJPEG stream to
`evidence/recordings/`. Requires WDA running.

Live view without recording: http://127.0.0.1:44321/phone

Do NOT use Apple's iPhone Mirroring app for this: it only mirrors while the
phone is locked, and the agent needs the phone unlocked.

## Hand the phone back

    ~/.iphone-use/setup-wda.sh pause     # stop WDA so the phone is usable by hand
    ~/.iphone-use/setup-wda.sh resume

## Useful

    launchctl kickstart -k gui/501/com.leeguoo.iphone-use   # restart daemon
    tail -f ~/Library/Logs/iPhoneUse/iphone-use.log
    ~/.iphone-use/uninstall.sh
