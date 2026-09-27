# Task: extract today's abusive messages from the "Team 2" chat

Run this only after `SETUP.md` is complete and `phone_status` reports drivable.
The person supervising watches live at http://127.0.0.1:44321/phone or in
QuickTime, and `scripts/record.sh team2` records the run.

## Procedure for the agent

1. `phone_screenshot` and describe the screen. If the phone is locked, stop
   and ask the supervisor to unlock it.
2. Go home (`phone_shortcut` home), open Messages (`phone_run_steps` with
   `launch_app` bundle `com.apple.MobileSMS`). Screenshot to confirm the
   conversation list is showing.
3. Read the list with `phone_elements`. Tap the conversation titled exactly
   "Team 2" (expected to be the top / most recent). If it is not visible,
   scroll the list once and look again. Do not open any other chat.
4. Screenshot the opened chat. Save it as `evidence/screens/<date>_00_open.png`.

Folders:
- `evidence/screens/`  every screenshot taken during the run, in order
  (`<date>_NN_<what>.png`). Complete record of what the agent saw.
- `evidence/flagged/`  only screenshots that visibly contain a flagged
  message. Copy the relevant screen from `screens/` and name it
  `<date>_<time>_<sender>.png`. This folder is the evidence set.
- `evidence/team2/`    the JSON index for that chat.
5. Walk the chat from the newest message upward:
   - Read visible bubbles with `phone_elements`. Note sender and text.
   - Swipe the message area left and hold briefly (`phone_run_steps` swipe,
     from x≈90% to x≈20% of the screen width) so per-message times appear,
     then screenshot. Save as `evidence/screens/<date>_NN_times.png`.
   - Release, then `phone_scroll` up by one screen and repeat.
   - Stop when a date separator earlier than today appears, or after 15
     screens, whichever comes first.
6. Never type, send, delete, react to, or forward anything. Read only.
7. Classify every message from today. Flag a message when it insults,
   threatens, humiliates, excludes, or pressures the phone owner, or
   encourages others to. Quote it exactly as shown. When unsure, include it
   with `confidence: "low"` rather than dropping it.
8. For each flagged message, copy the screenshot that shows it into
   `evidence/flagged/`. Then write `evidence/team2/team2_<YYYY-MM-DD>.json`
   (schema below), go home, and take a final screenshot.

## Output JSON

```json
{
  "chat": "Team 2",
  "date": "2026-09-25",
  "device": "Ava (iPhone 17)",
  "extracted_at": "2026-09-25T14:05:00-07:00",
  "screens_reviewed": 6,
  "messages_reviewed": 41,
  "flagged": [
    {
      "sender": "name as shown in the bubble header, or 'me'",
      "text": "exact message text",
      "time": "2:31 PM",
      "screenshot": "evidence/screens/2026-09-25_03_times.png",
      "flagged_copy": "evidence/flagged/2026-09-25_2-31PM_Jordan.png",
      "category": "insult | threat | exclusion | humiliation | pressure | other",
      "confidence": "high | medium | low",
      "why": "one sentence"
    }
  ]
}
```

Keep every screenshot referenced in the JSON. Screenshots are the evidence;
the JSON is the index.
