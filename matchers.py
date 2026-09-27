"""
HerProof — CDC-taxonomy matchers.

Classify each message against the coercive-control and expressive-aggression
items measured in the CDC's National Intimate Partner and Sexual Violence
Survey (NISVS 2023/2024).

Deliberately regex + counting. No model, no inference, no confidence score.
The output is always two things: the message, and why it was surfaced.
The survivor names what it was; a lawyer decides what it proves.

Attaching a category also attaches a published national prevalence figure,
which is the difference between "this tool thinks..." and "the CDC measures
this, and N% of women report it."

Usage:
    from matchers import classify
    cats = classify("i need to know where you are every hour")
    # -> [{"category": "Monitoring", "nisvs": "...", "prevalence": "18.6%",
    #      "span": "where you are"}]
"""

import re

# category -> (NISVS item text, women-lifetime prevalence, [regex patterns])
PREVALENCE_SOURCE = ("CDC, National Intimate Partner and Sexual Violence Survey "
                     "(NISVS) 2023/2024 IPV Data Brief, Table 7, lifetime prevalence among women")

# things a single message can't show about a survey item
CAVEATS = {
    "Degradation": "The survey item covers insults made in front of others; "
                   "a message alone does not show who else saw it.",
}
CATEGORIES = {
    "Financial control": (
        "Kept you from having your own money", "8.8%",
        [r"\b(my|the) money\b", r"you (can't|cant|don't|dont) (have|need|touch)\b.*\bmoney",
         r"\ballowance\b", r"\bstop spending\b", r"give (me|it) back", r"who (paid|pays) for"],
    ),
    "Isolation": (
        "Tried to keep you from seeing or talking to family or friends", "16.0%",
        [r"\bdon'?t (see|talk to|call|text)\b", r"\byour (family|friends|sister|mom)\b.*\b(again|anymore)\b",
         r"you (can't|cant) go", r"stay (home|away from)", r"\bnobody but me\b",
         r"\byou don'?t need (anyone|anybody) else\b"],
    ),
    "Monitoring": (
        "Kept track of you by demanding to know where you were", "18.6%",
        [r"where (are|were) you", r"who (are|were) you with", r"send (me )?(a )?(pic|photo|location)",
         r"share your location", r"\bevery (hour|minute)\b", r"why (aren'?t|didn'?t) you (answer|reply|pick up)"],
    ),
    "Threats of harm": (
        "Made threats to physically harm you", "12.4%",
        [r"\bi('| wi)ll (hurt|kill|find|end) you", r"you('?ll| will) (regret|be sorry)",
         r"\bwatch what happens\b", r"\b(ruin|destroy) your (life|career|reputation|job)\b", r"\byou('?re| are) dead\b", r"i know where you"],
    ),
    "Threatened self-harm": (
        "Threatened to hurt themselves or die by suicide", "14.0%",
        [r"\bi('| wi)ll (kill|hurt|end) myself\b", r"\bwithout you i('| wi)ll\b",
         r"\byou'?ll make me\b.*\b(hurt|kill)\b", r"\bit'?s your fault if i\b"],
    ),
    "Decisions taken": (
        "Made decisions that should have been yours to make", "15.2%",
        [r"\byou('?re| are) not (going|allowed)\b", r"\bi (already )?decided\b",
         r"\byou don'?t get to\b", r"\bi said no\b", r"\bthat'?s final\b"],
    ),
    "Property destroyed": (
        "Destroyed something important to you", "14.6%",
        [r"\bi (broke|smashed|threw out|burned|ripped)\b", r"\byour (phone|things|stuff)\b.*\b(gone|broken)\b"],
    ),
    "Degradation": (
        "Insulted, humiliated or made fun of you in front of others", "20.4%",
        [r"\byou('?re| are) (so |such )?(stupid|worthless|pathetic|nothing|ugly|a joke|useless)\b",
         r"\bnobody (else )?(would|will) (ever )?(want|love)\b", r"\beveryone (thinks|knows) you\b",
         r"\byou (useless|worthless|stupid|pathetic|idiot)\b", r"\b(more useful|better|smarter) than you\b"],
    ),
    # kept because survivors name it constantly, but NOT a NISVS item.
    "Reality denial": (
        None, None,
        [r"\bthat (didn'?t|never) happen(ed)?\b", r"\byou('?re| are) (imagining|remembering it wrong)\b",
         r"\bi never said that\b", r"\byou('?re| are) (so |being )?(crazy|paranoid|dramatic)\b"],
    ),
}


# iPhone text uses typographic quotes; the patterns are written with ASCII ones
QUOTES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"'})


def normalize(text):
    return text.translate(QUOTES).lower()


def classify(text):
    """Return a list of matched categories for one message's text."""
    if not text:
        return []
    lowered = normalize(text)
    hits = []
    for cat, (nisvs, prevalence, patterns) in CATEGORIES.items():
        for pat in patterns:
            m = re.search(pat, lowered)
            if m:
                hits.append({
                    "category": cat,
                    "nisvs": nisvs,                 # None for unmeasured (Reality denial)
                    "prevalence": prevalence,       # None for unmeasured
                    "measured": nisvs is not None,
                    "caveat": CAVEATS.get(cat),
                    "span": m.group(0),
                })
                break  # one hit per category is enough
    return hits


def enrich(messages):
    """Attach a `flags` list to every message. Only 'other'-sender messages
    are classified (the survivor is documenting what was said TO her);
    WhatsApp system notices and attachment placeholders are skipped."""
    for m in messages:
        if m.get("sender") == "other" and not m.get("attachment"):
            m["flags"] = classify(m.get("text", ""))
        else:
            m["flags"] = []
    return messages


def summary(messages):
    """Count flagged categories across all messages, with first/last occurrence
    and prevalence. Returns a list sorted by count desc."""
    agg = {}
    for m in messages:
        for f in m.get("flags", []):
            c = f["category"]
            rec = agg.setdefault(c, {
                "category": c, "count": 0, "first": None, "last": None,
                "prevalence": f["prevalence"], "measured": f["measured"],
                "nisvs": f["nisvs"], "caveat": f.get("caveat"),
            })
            rec["count"] += 1
            ts = m.get("timestamp") or m.get("approx_timestamp")
            if ts:
                rec["first"] = min(rec["first"], ts) if rec["first"] else ts
                rec["last"] = max(rec["last"], ts) if rec["last"] else ts
    return sorted(agg.values(), key=lambda r: -r["count"])


if __name__ == "__main__":
    for t in ["where are you and who are you with",
              "nobody else would ever want you",
              "that never happened, you\u2019re imagining it",
              "you\u2019re crazy"]:
        print(t, "->", [h["category"] for h in classify(t)])
