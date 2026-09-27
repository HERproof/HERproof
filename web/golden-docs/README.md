# Golden documents

The three records HerProof generates. One per audience, from the export spec in
the Pattern Map PRD.

| File | Audience | The thing it has to do |
|---|---|---|
| `01-lawyer.md` | Lawyer or DV advocate | Page 1 alone shows the shape of the pattern in under 2 minutes |
| `02-police.md` | Police | Establishes dates, sources and what was said, and asserts nothing else |
| `03-just-me.md` | The survivor herself | Private. Holds her own notes, which never appear in the other two |

## Rules that hold across all three

**Page 1 stands alone.** A lawyer with a queue may read nothing past it. Name, date
range, message count, source, time zone, summary sentence, weekly chart. In that order.

**HerProof's notes are not evidence.** Every automated tag lives in its own section, headed
"HerProof's notes, not evidence", never interleaved with the transcript. On by default for
lawyer and for her. Off and locked for police.

**The whole conversation, both sides.** Locked on for lawyer and police. Excerpts
invite a cherry-picking challenge and can be turned around on her. She can turn it off
only in her own copy.

**Gaps are not absence.** A period with no messages reads "No records for this period".
Never "nothing happened".

**Every footer carries** the page number and the source file SHA-256.

**The limits text on the last page is verbatim.** It is reproduced in each template and
is not reworded per document.

## Placeholders

`{name}` the other person, always the name she typed on import. Never "perpetrator",
never "abuser". `{category}` rows bind to HerProof's abuse type standard, not to the nine
CDC items the demo currently ships.
