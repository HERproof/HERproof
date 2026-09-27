# Golden document 4: the DVRO packet

The handoff version of the record, laid out so an attorney can work straight from it
when the next step is a domestic violence restraining order. Same record as golden
document 1, reordered around what the petition actually asks for.

California forms are the reference here because that is where our first clinics are.
The section order holds for other states; only the form numbers change.

## Who this is for

An attorney or a legal aid advocate who has an hour and has never met this person.
They should be able to open page one and know, without reading the appendix, who the
parties are, what the most recent incident was, what the pattern looks like, and where
every single assertion came from.

The survivor is not the reader. They see golden document 3.

## What this document never does

- It does not say abuse occurred. It says what was said, on what date, in what file.
- It does not score, rate, or rank anything.
- It does not recommend which orders to request. It lays out what the record supports
  and marks the call as the attorney's.
- It does not fill in a form field the record cannot support. A blank stays blank and
  appears in the review flags.

## Page order

**Page 1, cover.** Stands alone. Petitioner and respondent as named in the source files,
relationship, county, case number left blank, date prepared, the number of source files
and their fingerprints, incident count, date range covered. A one paragraph note saying
the document was assembled by software from files the petitioner supplied, that the
automated sections are marked, and that none of it is legal advice.

**Page 2, the most recent abuse.** DV-100 item 5 asks what happened most recently, and
that is what a judge reads first at an ex parte hearing. The three most recent incidents
in full: date, day of week, time, what was said or done, verbatim where the words matter,
and the source line. Nothing summarized.

**Page 3, the pattern.** Each kind of behavior found in the record, with how many times
it appears, the date it first appears, the date it last appears, and two dated examples.
This is the section that makes a course of conduct legible instead of anecdotal.

California recognizes coercive control in the Family Code definition of abuse, section
6320. Cite it here if the attorney wants it cited, and flag the citation for them to
confirm rather than printing it as settled.

**Page 4 onward, the chronology.** Every dated incident in order. One line each: date,
category, what happened, source. This is the body an attorney lifts into DV-101 or into
an MC-025 attachment when DV-100 runs out of room.

**Then, the evidence index.** Every source file: name, type, how it was produced, when it
was added, the period it covers, how many incidents came out of it, and its SHA-256. This
is the page that survives someone arguing the record was assembled after the fact.

**Then, the automated notes.** Anything the software inferred rather than read, in its own
section, headed so it cannot be mistaken for evidence. Off and locked for the police
version, on for this one, because an attorney is the right reader for it.

**Last, the appendix.** The full conversation, both sides, unedited, page numbered, with
the fingerprint in the footer of every page. Never excerpts. An excerpted thread is the
first thing opposing counsel attacks.

## Field mapping

| Form | What it asks | What we hand over |
| --- | --- | --- |
| DV-100 item 4 | Relationship to respondent | Cover page, from what the survivor entered, never inferred from the messages |
| DV-100 item 5 | Most recent abuse | Page 2, the three most recent incidents |
| DV-100 item 5, past abuse | Other abuse | Page 4 chronology, plus the pattern page |
| DV-101 | Description of abuse, dated list | The chronology, already in the order the form wants |
| MC-025 | Attached declaration when the box is too small | The chronology and appendix as attachments, page numbered |
| CLETS-001 | Respondent identifiers | Left blank with a review flag. The record does not reliably hold a date of birth, a vehicle, or a physical description, and guessing on a law enforcement form is worse than leaving it empty |
| DV-105 | Children, custody | Flagged only if the record mentions children. Never populated automatically |
| DV-108 | Stay-away from a workplace or school | Flagged where the record shows the respondent naming a workplace, school, or routine |
| DV-110 item on firearms | Firearms | Flagged where the record mentions a weapon, in the respondent's own words, quoted |

## How an incident renders

```
2026-08-14  08:31  Money control
"I changed the login on the joint account. ask me if you need grocery money."
WhatsApp Chat with Sam.txt, line 1,412   sha256 4f9c2ae1...
Date established from the export timestamp. Format dd/mm/yyyy confirmed from the file.
```

Rules that do not bend:

- Verbatim quotes are capped at the length needed to carry the meaning, and truncation is
  marked. A quote is never tidied, corrected, or rewritten.
- Every incident carries how its date was established, not just the date.
- A period with no messages reads "No records for this period." It never reads as calm, and
  it is never left as an unexplained gap in the chronology.
- If the software is unsure whether something belongs in a category, it does not appear in
  the pattern counts. It appears in the chronology only.

## Attorney review flags

Collected on one page at the front, not scattered:

- Fields the petition needs that the record cannot supply, named individually.
- Incidents where the date could only be established from the file's own metadata.
- Anything in the record that reads as a threat to life or a weapon reference, listed
  separately and never softened, so it is seen before the hearing rather than found later.
- Every place the software inferred a category, with the confidence it had.
- Anything the survivor removed, shown as removed, so the attorney knows the record was
  edited and by whom.

## The line this document holds

HerProof prepares the paperwork. It does not file it, it does not advise on it, and it does
not decide what to request. The hour an attorney gets with a survivor is expensive and
usually the only one, and this document exists so that hour is spent on judgment rather
than on data entry.

HerProof is not a law firm and does not give legal advice. It gets you ready for a lawyer and a
therapist, and hands them the record.

You can delete any of it, or all of it, whenever you want. You can talk to her without
saving a word. Quick Exit is always one tap away, and leaving takes nothing more than
closing the app.
