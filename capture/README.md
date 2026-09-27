# Her_Proof

Document cyberbullying and abusive messages on an iPhone, from a Mac, without
touching the phone by hand. The tool opens Messages, walks one conversation
from newest to oldest, saves a screenshot of every screen (including a second
one with per-message times revealed), flags the abusive messages, and writes a
JSON index that points each flagged message at the screenshot that proves it.

Read-only by design: it never types, sends, reacts, forwards, or deletes.

```
   Mac                                    iPhone (USB, unlocked)
   ─────────────────────────────────      ────────────────────────
   herproof/extract.py  ──HTTP──►  iphone-use daemon  ──►  WebDriverAgent  ──►  Messages app
   (or Claude Code via MCP)          :44321                 :8100 / :9100
```

## What you need

- A Mac on macOS 15 or newer with **full Xcode** (not just Command Line Tools),
  signed in to an Apple ID under Xcode > Settings > Accounts. A free Apple ID
  works; a paid developer account avoids the 7-day re-signing.
- Homebrew.
- The iPhone, a USB cable, and the phone owner's cooperation: the phone must be
  unlocked the whole time, with Developer Mode on.
- An API key for the classifier: Anthropic (Claude) or Google (Gemini).
  Optional; without either a keyword heuristic runs instead.

## Install (once per Mac)

```sh
git clone <this repo> Her_Proof && cd Her_Proof
sh setup/install.sh
```

The installer does, in order: checks Xcode and your signing certificate,
derives your Team ID from the certificate, installs libimobiledevice and
ffmpeg, installs the [iphone-use](https://github.com/leeguooooo/iphone-use)
daemon, patches a bug in its WDA setup script, downloads Xcode's iOS platform
if missing, checks the phone is trusted and in Developer Mode, writes `.env`,
registers the phone in your developer account, builds and installs
WebDriverAgent, registers the MCP server with Claude Code if present, and
creates a Python virtualenv. It stops with a clear message whenever a step
needs you (plug in the phone, enable Developer Mode, trust the profile) and is
safe to re-run.

Things the installer cannot do for you:

| Step | Where |
|---|---|
| Sign in to Xcode | Xcode > Settings > Accounts > + |
| Developer Mode | iPhone: Settings > Privacy & Security > Developer Mode (appears after the first USB connection; `idevicedevmodectl reveal` forces it) |
| Trust This Computer | iPhone prompt on first USB connection |
| Untrusted Developer | iPhone: Settings > General > VPN & Device Management |
| Keep the phone awake | iPhone: Settings > Display & Brightness > Auto-Lock > Never |

## Run

```sh
source .venv/bin/activate
python -m herproof.extract --chat "Team 2"           # flag today's messages in that chat
python -m herproof.extract --chat "Team 2" --all-days
python -m herproof.extract --chat "Team 2" --provider gemini   # or claude; default: whichever key is set
python -m herproof.extract --chat "Team 2" --no-classify       # no API key: keyword heuristic
```

### Choosing the model

The phone navigation is deterministic code and needs no model. The model is
used once per run, to judge which messages are abusive, through one function
in `herproof/llm.py` that both providers implement with the same prompt and
JSON schema.

| Provider | Credentials in `.env` | Default model | Override |
|---|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` (or `ant auth login`) | `claude-opus-5` | `--model` or `ANTHROPIC_MODEL` |
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `gemini-2.5-pro` | `--model` or `GEMINI_MODEL` |

`--provider auto` (the default) picks Claude if its key is present, else
Gemini. Set `HERPROOF_PROVIDER=gemini` in `.env` to make Gemini the default.
If the model call fails for any reason the run still completes with the
keyword heuristic and says so in the JSON's `method` field; set
`HERPROOF_STRICT=1` to make that a hard error instead.

Output, all under `evidence/`:

- `screens/` every screenshot in order: `<date>_<NN>_<what>.png`. Screens ending
  in `_times` were captured mid-swipe with the time shown next to each bubble.
- `flagged/` one screenshot per flagged message, named by time, sender, and the
  start of the text. This folder is the evidence set.
- `<chat>/<chat>_<date>.json` the index: each flagged message with exact text,
  time, category, confidence, a one-line reason, and both screenshot paths;
  the phone owner's own replies that show impact; and the full timeline.

Watch it live: QuickTime Player > File > New Movie Recording, then pick the
iPhone in the camera dropdown. Press record there to keep a video. (Apple's
iPhone Mirroring app does not work here: it only mirrors a locked phone.)

When you are done, give the phone back:

```sh
~/.iphone-use/setup-wda.sh pause     # stop the agent so the phone is usable by hand
~/.iphone-use/setup-wda.sh resume    # before the next run
```

## Model-driven mode (any app, any provider)

`herproof.extract` is fixed code for one job: walk one iMessage chat. When the
job is different (Instagram DMs, a group in another app, "look through the
last five chats"), let a model drive instead:

```sh
python -m herproof.agent --chat "Team 2"                        # same job, model-driven
python -m herproof.agent --chat "Team 2" --provider gemini
python -m herproof.agent --provider claude \
    --goal "Open Instagram, go to Messages, open the chat with 'jess', review it from newest to oldest, flag abusive messages, finish."
python -m herproof.agent --chat "Team 2" --provider scripted    # no API key: fixed procedure through the same tools
```

The model gets the phone as tools (`herproof/tools.py`): `phone_status`,
`read_screen`, `screenshot`, `screenshot_with_times`, `tap_element`, `tap`,
`scroll`, `home`, `launch_app`, `back`, `flag_message`, `finish`. That is the
same set Claude Code gets through the iphone-use MCP server, so anything you
can do interactively in Claude Code, this mode does headless, on whichever
provider you choose. `herproof/agent.py` holds one loop per provider (Claude
tool use, Gemini function calling) and a `scripted` stand-in that replays the
Messages procedure through the same tools for testing without a key. Output is
`evidence/<chat>/<chat>_<date>_agent.json` plus the usual `screens/` and
`flagged/` folders.

Cost and reliability: the model-driven mode makes one model call per action,
with screenshots as images, so a full chat walk is dozens of calls. Prefer
`herproof.extract` whenever the job is the fixed iMessage walk.

## Feeding the HerProof pipeline

Every run also writes `evidence/<run>/entries.json`: one entry per screenshot,
in the shape the repo's `ingest.py` produces, with `source_type` set to
`iphone_capture`, every message stamped with the time iOS showed for it on
the capture date, confidence 1.0, and the capture's judgment on each message
as `capture_flag`. Overlap between screens is already removed, so each message
belongs to exactly one screenshot (the one where it is most visible).

End to end, from the repo root (`organize.py` needs `GEMINI_API_KEY` in the
root `.env` for the incident summaries; everything else runs without a key):

    cd capture
    .venv/bin/python -m herproof.extract --chat "Alex" --out evidence/alex
    cd ..
    cp capture/evidence/alex/entries.json entries.json
    python organize.py                                  # -> timeline.json
    python export_packet.py capture/evidence/alex/screens   # -> packet.html
    open packet.html                                    # Download as PDF

| Step | Command | Reads | Writes |
|---|---|---|---|
| 1 capture | `herproof.extract --chat X --out evidence/X` | the phone | `evidence/X/screens/*.png`, `flagged/`, `X/X_<date>.json`, `entries.json` |
| 2 organize | `organize.py` | `./entries.json` | `./timeline.json` |
| 3 packet | `export_packet.py capture/evidence/X/screens` | `entries.json`, `timeline.json`, the screenshots | `./packet.html` |

The packet includes every message the CDC matchers hit plus every message
flagged at capture (labelled "Flagged at capture" in the Kind column), and
embeds each captured screenshot as an exhibit with its SHA-256 re-verified.

`entries.json`, `timeline.json` and `packet.html` at the repo root are the
committed demo data. Running the pipeline overwrites them; restore with
`git checkout -- entries.json timeline.json packet.html` before committing,
or run the three commands in a scratch copy of the root `.py` files.

Known limit: with `--all-days`, messages from earlier days still get the
capture date, because iOS only shows a clock time per bubble. Re-run per day
or fix the dates in `entries.json` before organizing.

## Showing a capture in the web UI (Pattern Map)

Every run also writes `messages.txt` (the Pattern Map import format) and
`capture-tags.json` (the capture's flags keyed by line) next to
`entries.json`. Serve the repo and load the run by name:

    cd <repo root> && python3 -m http.server 8000
    open http://localhost:8000/web/pattern-map/index.html

Import a conversation, type the run folder name (for example `alex`), press
"Load capture", pick who is you, press Start. The map then shows the
captured chat with the capture's flags merged into the keyword tags, marked
`model: "capture"`, plus whatever the page's own keyword pass finds. The
app's DVRO step (`web/pattern-map/app.html`) links to the
`packet.html` the pipeline generated at the repo root.

### The six-step app, live (`web/pattern-map/app.html`)

Run the demo server instead of `http.server`; it serves the site and adds the
capture API:

    cd <repo root>
    capture/.venv/bin/python capture/server.py        # http://localhost:8000
    open http://localhost:8000/web/pattern-map/app.html

Demo script:

1. **Hello.** Type what is going on, e.g. "my coworker Alex is bullying me".
   The app picks the name out of the sentence (any saved run's chat name, or
   a capitalised name after words like coworker / with / boss) and answers.
2. **Your account.** First name and a PIN, no email. The PIN is prefilled
   with 1111 for the demo.
3. **Connect.** The light under the cable picture is grey until this Mac sees
   the iPhone on USB (amber), and turns green when the phone is unlocked and
   ready. Press "My iPhone is connected and unlocked". By default the demo
   does **not** capture live: it plays a screen recording of the agent going
   through the phone while the saved run loads behind it, and the progress
   bar follows the video. Put the recording at
   `capture/evidence/<run>/recording.mp4` (H.264 MP4 or WebM) and it is
   picked up automatically. iPhone and QuickTime recordings are usually HEVC,
   which not every browser plays; convert once with

       ffmpeg -i ~/Desktop/0925.mp4 -vf "scale=-2:1280,format=yuv420p" -c:v libx264 \
         -profile:v main -crf 22 -movflags +faststart -an capture/evidence/alex/recording.mp4

   Without a file there, a file picker appears on the Connect step and the
   chosen file stays on this computer. With no recording at
   all, a three-second animation runs instead. If the video cannot start
   within six seconds the animation takes over, so the demo never hangs.

   Add `?live=1` to the URL to run the real capture instead: the server runs
   `herproof.extract`, `organize.py` and `export_packet.py` and the bar reads
   the live phase (a chat walk takes about a minute and a half). If the phone
   is not drivable it falls back to the saved run.
4. **What came across.** Every screenshot the capture took, in order; the
   ones that contain a flagged message are outlined with a "N flagged" badge,
   the Messages list and home screen are dimmed.
5. **Working through it, The map, DVRO packet.** All rendered from the data:
   category counts, the Gemini incident summary, the DV-100 item 5 box filled
   from the strongest messages, and the packet link opening the generated
   `packet.html`.

`?chat=Alex` pre-names the chat and `?run=<folder>` forces a saved run. With
a plain static server (no API) the flow uses the saved run automatically.

## Driving the phone interactively with Claude Code

The installer registers the `iphone-use` MCP server for Claude Code. Open
Claude Code in this folder and ask it to take a screenshot, open Messages, and
so on. `tasks/team2-today.md` is the procedure it should follow for an
evidence pass. `scripts/` holds the small helpers used in that mode:
`snap.sh` (save a screenshot), `times_snap.sh` (timestamp-reveal capture),
`record.sh` (record the agent's video stream).

## How it works, and the traps we hit

- **Text, sender, and time come from the accessibility tree**, not OCR. Each
  Messages bubble is exposed as `"<sender>, <text>, <h:mm AM/PM>"`. The
  screenshots are the human-readable proof; the JSON is the index.
- **Per-message times are only visible mid-gesture.** iOS shows them while
  you drag the transcript left. The daemon queues screenshots behind gestures,
  so a normal screenshot always lands after the release. `Phone.capture_times`
  records the daemon's MJPEG stream during a slow drag and keeps the frame that
  differs most from the resting screen.
- **Owner lock.** The daemon lets one owner drive at a time. Raw HTTP calls
  must send `X-Phone-Owner`, and it must match if a Claude Code MCP session
  is also open. Close Claude Code, or set `PHONE_REMOTE_OWNER` to that
  session's owner id (`mcp-<pid>`), before running the extractor.
- **Tapping a conversation.** The list exposes two nested cells with the same
  label, so element taps are ambiguous; the code taps by position and retries
  once because the first tap on iOS 26 can just collapse the large title.
- **setup-wda.sh proxy bug.** On a Mac that never configured a system proxy
  the script aborts, and its launchd supervisor then loops forever. Fixed by
  `setup/patch-setup-wda.sh`; re-apply after any iphone-use reinstall.
- **Device registration.** With an Apple-ID login the setup script never
  passes `-allowProvisioningDeviceRegistration`, so a brand-new phone fails
  with "isn't registered in your developer account". The installer runs one
  xcodebuild with that flag first.
- **Team ID.** The 10-character code in the certificate's display name is not
  the team. Use the `OU` field, which the installer reads for you.
- **Two paired iPhones** make the setup script refuse to guess; `.env` pins
  `WDA_UDID`.

## Repo layout

```
herproof/           phone.py HTTP client · messages.py parser · llm.py providers
                    classify.py prompt + heuristic · extract.py deterministic CLI
                    tools.py phone tools for a model · agent.py model-driven CLI
setup/install.sh    one-shot Mac setup with every fix above
setup/patch-setup-wda.sh
scripts/            helpers for the interactive (Claude Code) mode
tasks/              procedure the interactive agent follows
SETUP.md            notes from the first machine this was set up on
evidence/           output (gitignored)
```

## Ethics and consent

This exists to help a victim document abuse directed at them. It requires the
phone unlocked and in Developer Mode, which cannot happen without the owner's
participation. Do not use it on a phone you do not have permission to access.
