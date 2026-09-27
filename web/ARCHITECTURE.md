# HerProof architecture

The idea: point a tool at a message archive, leave it running, get back something a
lawyer can actually use. Four stages, message archive to
lawyer-ready record.

It is built around a survivor rather than a litigant, which changes two things.

**Nothing leaves the device.** A tool that asks you to connect your iPhone to a
computer and wait an hour assumes you can. A survivor often cannot: the abuser may have access
to the laptop, the phone, or the account. So every stage here runs in the browser tab.
No upload, no account, no network call after the page loads. Close the tab and the
evidence is gone from the machine.

**The taxonomy is the CDC's, not ours.** Flagged messages are classified against the
coercive control and expressive aggression items measured in the CDC's National
Intimate Partner and Sexual Violence Survey, 2023/2024. That gives every category on
the report a published national prevalence figure, which is the difference between
"this tool thinks your ex was controlling" and "this pattern is one the CDC measures,
and 18.6% of women report it."

## Stages

    1. INGEST        paste or drop a message export
                     parse iMessage / WhatsApp / generic "Name: text" formats
                     normalise to { ts, sender, text }
                     -> in memory only

    2. FLAG          per-message matchers, one per CDC category
                     plus structural signals that no keyword can catch
                     (unanswered rapid bursts, late-night contact volume)
                     -> messages of interest, each with category + matched span

    3. ANALYSE       counts and first/last occurrence per category
                     contact rhythm over time
                     national prevalence attached per category
                     -> pattern summary

    4. EXPORT        Markdown record: summary, then every flagged message
                     verbatim with its timestamp and why it was flagged
                     -> download, or print to PDF

Stage 4 is the product. Stages 1 to 3 exist to make stage 4 survive a lawyer reading it.

## What the matchers are, honestly

Regular expressions and counting. No model, no inference, no score.

That is a deliberate ceiling, not a stopgap. A tool that tells a survivor "you were
abused, confidence 0.87" has taken the naming away from her and handed her something
she cannot take to court either. So the output is always the same two things: the
message, and the reason it was surfaced. She decides what it was. A lawyer decides
what it proves.

It also means no message ever needs to be sent to a model, which is what keeps stage 1
honest.

## Report categories

Seven map to a measured NISVS item. Two do not, and say so on the report.

| Category | NISVS item | Women, lifetime |
|---|---|---|
| Financial control | Kept you from having your own money | 8.8% |
| Isolation | Tried to keep you from seeing or talking to family or friends | 16.0% |
| Monitoring | Kept track of you by demanding to know where you were | 18.6% |
| Threats of harm | Made threats to physically harm you | 12.4% |
| Threatened self-harm | Threatened to hurt themselves or die by suicide | 14.0% |
| Decisions taken | Made decisions that should have been yours to make | 15.2% |
| Property destroyed | Destroyed something important to you | 14.6% |
| Degradation | Insulted, humiliated or made fun of you in front of others | 20.4% |
| Reality denial | not a NISVS item | not measured |

Source: CDC NISVS 2023/2024 Intimate Partner Violence Data Brief, Table 7.
Reality denial is kept because survivors name it constantly and it is what makes the
rest hard to report, but the report marks it as unmeasured rather than borrowing a
number that does not describe it.

## Where this goes next

- Real export parsers: iMessage `chat.db`, WhatsApp `_chat.txt`, Android SMS XML.
- Per-category matcher packs that a domestic violence advocate can edit without touching code.
- Optional on-device model for paraphrase matching, only if it can run offline.
- A second report type aimed at a protection order petition rather than a lawyer.

## Not legal advice

This is not a law firm and does not give legal advice. It gets you ready for a lawyer
and a therapist, and hands them the record.

You can delete any of it, or all of it, whenever you want. Nothing is saved anywhere
but the tab you have open, and closing the tab is all it takes to leave.
