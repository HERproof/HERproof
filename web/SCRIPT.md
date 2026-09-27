# HerProof, 3 minute demo script

One page, one link: `web/index.html`. Landing on top, Cora and the whole flow underneath. Press F for full screen, arrow keys to move, D to disguise.

## Before you start
- Open the page and leave it on the landing.
- Sound on. `config.js` sits next to the page with the Gemini key, so Cora speaks in her own voice.
- Serve the repo with `capture/.venv/bin/python capture/server.py` and open `http://localhost:8000/web/index.html`.
- Have `packet.html` at the repo root (the one the pipeline generated from Alex) open in a second tab in case a judge asks to see the filled forms.

---

## 0:00 to 0:25 The problem, on the landing

"A survivor already has the proof. It is two years of messages, photos, a note she wrote at 2am, scattered across her phone where nobody can read it. Getting a restraining order means reliving all of it and turning it into a declaration. Most people stop there."

Scroll once. The pile of files on the left tidies itself into a dated record on the right.

"Same evidence. One version nobody can use, one an attorney can read in ten minutes."

## 0:25 to 0:50 Meet Cora

Click **Meet Cora**. The page goes full screen, she walks in and starts talking.

"This is Cora. She speaks with Gemini, the transcript lands a line at a time, and you can type to her instead if reading is easier or the room is not safe."

Cora asks two things. Type *have an issue with Alex* and press Send; she asks when.
Type *today* and press Send; she says to plug the iPhone in, and the button becomes
**My iPhone is ready**. (The name comes from your sentence; any chat captured before works.)

"She never asks a survivor to retell it."

## 0:50 to 1:15 Account and cable

"The PIN she picks is the encryption key. It is derived on her machine, we never hold it, and there is no reset, because a reset is a door someone else can walk through."

The light under the cable picture goes green when this Mac sees the iPhone unlocked. Press
**My iPhone is connected and unlocked** and keep talking while it fills: the screen recording of
the agent going through her phone plays in the frame, and the bar follows it. (The demo server,
`capture/server.py`, must be running, and the recording sits at `capture/evidence/alex/recording.mp4`.)

"Her phone comes across once. Everything is encrypted into her vault as it lands, dates taken from the files themselves, and nothing is uploaded."

On **What came across**, every screenshot the agent took is shown, the ones with flagged
messages outlined. Wait a beat: "Then the photo library" scans the Photos grid and surfaces
the two injury photos, small, badged Injury. Say: "It read the photo library the same way,
and left every other photo alone."

## 1:15 to 1:50 Gemini reads it

Let the agent list tick and the Gemini panel stream.

"Gemini does three jobs. Date order. Sorting into six categories that map to the CDC's national violence survey, the same six our codebase uses. Then it writes each form answer in his own words, with the line and the timestamp it came from."

Point at two lines on the stream:

"2,131 ordinary messages were left out on purpose. And the empty months are marked missing, never calm."

## 1:50 to 2:15 The map

"Forty-seven dated incidents across nineteen months. Monitoring eighteen, degradation nine, decisions taken eight, isolation seven. Each carries the national prevalence beside her own count, so a judge sees a pattern rather than a bad week."

## 2:15 to 2:45 The packet

"Item 5 of the DV-100 is the box that stops people. On the left the blank form, on the right the same box filled from her own record."

Then point at CLETS-001.

"His date of birth and plate are not in what she gave us, so they stay blank. A guess on a form the police act on is worse than a blank."

Unlock the vault with the PIN, 4821.

"Every item keeps the fingerprint taken when it arrived, so an attorney can show nothing was edited. Delete means gone from this machine."

## 2:45 to 3:00 Send, and safety

"Sealed to her attorney's public key before it leaves. There is no copy on our side for anyone to subpoena. And nothing has been sent. The send button is hers."

Press **D**. The screen becomes a recipes app.

"One tap and it is recipes. Quick Exit wipes the screen and opens LinkedIn. That is the whole design: she decides, we just get it ready for a lawyer."

---

## If a judge asks

**Is the encryption real?** It runs locally end to end today, and the key handling is in the flow you just watched. An independent security review is the next step before anyone relies on it in a real case. We would rather say that than claim an audit we do not have.

**Where does the AI stop?** It names and it sorts. It never decides what happened to her and never writes a sentence he did not say. The survivor says what it was, and a lawyer decides what it proves.

**Why those six categories?** They come from the CDC's National Intimate Partner and Sexual Violence Survey, so each carries a real national prevalence and the taxonomy is jurisdiction-agnostic.

**Is it built?** The flow is wired and running: real Judicial Council PDFs, real field mapping, a fingerprint on every item. The California forms are the ones the court publishes.

HerProof is not a law firm and does not give legal advice. It gets your record ready for a lawyer and hands it over.
