# Record of messages

**Prepared by** {client_name} using HerProof · **For** {recipient_name}, {firm}
**Other person as named by the client:** {name}
**Period** {first_date} to {last_date} · **Messages** {total} · **Source** {source}, exported {export_date}
**Time zone applied** {iana_zone} · **Source file SHA-256** {sha256}

## What the record shows

Over {weeks} weeks, {n_tagged} messages from {name} were tagged across {k} kinds of
behavior. Tagged messages went from about {avg_first_4} a week in {first_month} to
about {avg_last_4} a week in {last_month}.

{gap_sentences}

### Tagged messages per week

{weekly_chart}

Weeks rendered hatched are periods with no records in either direction. No records for
a period is not a record of nothing happening.

---

## Behavior over time

{behavior_timeline}

One row per category, one dot per tagged message.

## Categories

| Category | Messages | First seen | Most recent |
|---|---|---|---|
| {category} | {count} | {first} | {latest} |

## Timing

Computed from timestamps, without AI.

- {pct_other}% of messages in the thread were sent by {name}.
- {pct_night}% were sent between 11pm and 3am.
- Longest burst: {burst_n} messages from {name} within {burst_window} minutes with no reply.

---

## HerProof's notes, not evidence

Automated descriptions of the tagged messages. They are not findings, and they are not
part of the evidence. The client reviewed every one and removed any she marked as not
accurate.

| Line | Date | Category | Why it was tagged |
|---|---|---|---|
| {line_no} | {ts} | {category} | {reasons} |

---

## Full conversation

Both senders, in date order, with line numbers and date confidence. Tagged rows carry a
category key only. The whole conversation is included rather than excerpts, so the
record cannot be read as selected.

| Line | Date and time | Sender | Message | Conf. | Tag |
|---|---|---|---|---|---|
| {line_no} | {ts} | {sender} | {body} | {date_confidence} | {category_key} |

---

## How the dates were established

{n_high} messages carry an export timestamp with seconds (High). {n_medium} carry an
export timestamp to the minute (Medium). {n_low} could not be established from the
export itself (Low).

Low confidence means the date could not be established well, not that the item is
doubtful.

Date order was {date_order_method}. Times are shown in {iana_zone}, which the client
selected on import; WhatsApp exports carry no offset of their own.

## What this record does not establish

This record shows the dates and times that could be established for each message and
where each came from. It does not establish who wrote any message, what any message
means, or that any statement in it is true. Times recorded by WhatsApp are the
platform's record rather than verified fact. HerProof's notes are automated descriptions,
not findings. Nothing here is a legal conclusion or legal advice.

*Page {page} of {pages} · Source SHA-256 {sha256_short}*
