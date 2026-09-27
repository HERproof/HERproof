# HerProof

**Your story. Your proof.**

HerProof turns the evidence already on a survivor's phone (messages, screenshots, photos)
into a dated, fingerprinted record an attorney can read in ten minutes, and into a
California domestic violence restraining order (DVRO) packet.

- Sorts what repeats into the six kinds of behavior the CDC measures in its national survey.
- Flags stretches of time with no messages as missing evidence, so a gap is never read as "nothing happened".
- Never writes a sentence anyone did not say.

HerProof is not a law firm and does not give legal advice. It gets the record ready for a
lawyer and hands it over.

> All data in this repo is staged for the demo. No real survivor's data is here.

---

## Try it

**[herproof.github.io/HERproof](https://herproof.github.io/HERproof/)**

Opens the app in your browser. Nothing to install.

| Key | Does |
|---|---|
| ← → | Move between steps |
| F | Full screen |
| D | Disguise the screen as a recipes app |

### Pages you can open directly

| Page | What it shows |
|---|---|
| [The app](https://herproof.github.io/HERproof/web/pattern-map/app.html) | Cora walks through the whole flow: account, connect, what came across, the pattern map, the DVRO packet, send to an attorney |
| [DVRO packet](https://herproof.github.io/HERproof/web/pattern-map/packet.html) | DV-100 filled, CLETS-001 left blank on purpose, flagged forms, 47 dated incidents, exhibit list |
| [The pattern](https://herproof.github.io/HERproof/web/pattern-map/pattern.html) | Month heat grid, timeline with the gap, clusters |
| [Vault](https://herproof.github.io/HERproof/web/pattern-map/vault.html) | Sources, fingerprints, dated incidents |
| [Photo exhibits](https://herproof.github.io/HERproof/web/pattern-map/exhibits.html) | Photos with dates and fingerprints |
| [Forms by state](https://herproof.github.io/HERproof/web/pattern-map/jurisdictions.html) | Restraining order forms by state, leading into the California forms |
| [Generated record](https://herproof.github.io/HERproof/packet.html) | The record the pipeline last generated from the sample screenshots |
| [Presentation view](https://herproof.github.io/HERproof/web/index.html) | The app with the landing page on top, for live demos ([script](web/SCRIPT.md)) |

### Run it on your computer

The online version stops at the **Connect** step, because reading a phone needs a computer
running HerProof. For the full demo:

```
git clone https://github.com/HERproof/HERproof.git
cd HERproof
python3 capture/server.py
```

Leave that running, then open http://localhost:8000 in a new browser tab.

| Part | What it needs |
|---|---|
| Connect step onward | A saved phone capture in `capture/evidence/<name>/`, which is not in the repo because it holds phone data. Make one (see [Capture from an iPhone](#capture-from-an-iphone)). Without it the app says *"Could not read the capture for alex"*. |
| Cora's Gemini voice | Optional. Copy `web/pattern-map/config.example.js` to `config.js` and add a Gemini key. Without it Cora uses the browser's voice. |

Always start the server from the `HERproof` folder, and open pages through it rather than
double-clicking the files.

---

## How it works

```
  iPhone (capture/)  ─┐
                      ├─►  entries.json  ─►  organize.py  ─►  timeline.json  ─►  export_packet.py  ─►  packet.html
  folder (ingest.py) ─┘                                                                                   │
                                                                   web/ app shows the record and packet  ◄─┘
```

1. **Collect.** `capture/` reads a conversation straight off an iPhone, or `ingest.py`
   reads a folder of screenshots and WhatsApp exports. Every file gets a SHA-256 fingerprint.
2. **Organize.** `organize.py` dates and sorts every message, tags the patterns with fixed
   rules (no AI), groups incidents and flags anything to check by hand.
3. **Export.** `export_packet.py` builds `packet.html`, ready to save as a PDF.
4. **Show.** `web/` is the app the survivor uses.

## Project layout

| Folder | What's in it |
|---|---|
| repo root | The pipeline: `ingest.py`, `organize.py`, `export_packet.py` and their helpers, plus their output (`entries.json`, `timeline.json`, `packet.html`) |
| `capture/` | Reads an iPhone from a Mac, and the demo server (`server.py`) |
| `web/` | The app, its pages, and the design docs |
| `samples/` | Demo data |
| `docs/` | [How it works](docs/how-it-works.md): every file explained |

---

## Run the pipeline

Needs Python 3.10+ and a Gemini API key in a `.env` file at the root (`GEMINI_API_KEY=...`).

```
pip install -r requirements.txt
python ingest.py ./samples          # -> entries.json
python organize.py                  # -> timeline.json
python export_packet.py ./samples   # -> packet.html
```

### Capture from an iPhone

Mac only. One-time setup is in [`capture/README.md`](capture/README.md).

```
cd capture && sh setup/install.sh
.venv/bin/python -m herproof.extract --chat "Alex" --out evidence/alex   # phone plugged in and unlocked
cd .. && cp capture/evidence/alex/entries.json entries.json
python organize.py && python export_packet.py capture/evidence/alex/screens
```

## Privacy

`ingest.py` and `organize.py` send screenshots and message text to Google's Gemini API.
Check its data terms before using real evidence, and uncomment the data lines in
`.gitignore` so real evidence can never be pushed.

## If you need help

US National Domestic Violence Hotline: **1-800-799-7233**, or text START to 88788.

## License

MIT, see [LICENSE](LICENSE).
