#!/usr/bin/env python3
"""D1 — patient age / life-stage. The cheapest dimension: a pure text edit (swap the stated
age and entailed phrasing), no data synthesis. Detection is regex; the editor reuses the
robust deterministic-swap + verified-LLM-extras logic from edit.py.
"""
import re

import edit  # the existing age editor (edit_one) — reused verbatim
from dimensions.base import Dimension

# Conservative year-age patterns (avoid bare "I'm 34" and month/week-old infants).
_AGE_PATTERNS = [
    re.compile(r"\b(\d{1,3})[\s-]*(?:years?|yrs?)[\s-]*old\b", re.I),
    re.compile(r"\b(\d{1,3})\s*[- ]?(?:yo|y/o|y\.o\.)\b", re.I),
    re.compile(r"\bage[d]?\s*(?:of|is|:)?\s*(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})[- ]year[- ]old\b", re.I),
]

# Life-stage anchors for the sweep (child, young adult, elderly), backfilled to reach K.
_AGE_ANCHORS = [8, 30, 72]
_AGE_BACKFILL = [50, 16, 85]

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if ONLY the patient's age
changes — from {age_from} to a clearly different age (we will test ages {values}).
Everything else about the case is identical.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way after
the age change — i.e. whether its correct pass/fail verdict is unchanged at every tested age
versus age {age_from} — and classify it:
- "kept": still valid the same way — a good answer's pass/fail verdict for this item does not
  change with age. This INCLUDES items whose emphasis, strength, threshold, or expected level of
  detail would merely shift: we are NOT tracking weighting, only whether the verdict changes.
- "moot": it rewards asking for / seeking / confirming information that the new age makes
  irrelevant or unnecessary.
- "change": the age changes whether a good answer satisfies the item — the substantive content a
  good answer must have changes (differential, dose, screening, contraindication, management).
  This INCLUDES an item that itself grades the response's level of urgency / triage / red-flags /
  referral, when the appropriate level changes with age.
Be conservative: use "kept" unless a SPECIFIC age-driven clinical reason changes the verdict.
A mere shift in weighting / emphasis / threshold is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Also propose any NEW criteria a good answer should now satisfy specifically because of the
age change (e.g. geriatric falls/polypharmacy at an older age; growth/development or guardian
involvement at a younger age). Keep them specific and checkable.

# Conversation (original, age {age_from})
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|change",
                    "sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""


def detect_age(messages):
    text = "\n".join(m.get("content", "") for m in messages if m.get("role") != "assistant")
    for pat in _AGE_PATTERNS:
        for m in pat.finditer(text):
            age = int(m.group(1))
            if 0 < age <= 120:
                return age, m.group(0).strip()
    return None


def pick_target(age, forced=None):
    if forced:
        return forced
    if age < 18:
        return 45
    if age < 50:
        return 72
    return 28


def sweep_ages(base, k=3, min_gap=10, sep=5):
    vals = [a for a in _AGE_ANCHORS if abs(a - base) >= min_gap]
    for extra in _AGE_BACKFILL:
        if len(vals) >= k:
            break
        if abs(extra - base) >= min_gap and all(abs(extra - v) >= sep for v in vals):
            vals.append(extra)
    return sorted(vals)[:k]


class AgeDimension(Dimension):
    name = "age"

    def detect(self, ex):
        hit = detect_age(ex["messages"])
        if not hit:
            return None
        age, age_str = hit
        return {"dimension": self.name, "base_value": age, "age_from": age, "age_str": age_str,
                "target_age": pick_target(age), "label": f"age {age}"}

    def values(self, s):
        return sweep_ages(s["age_from"])

    def edit_one(self, messages, s, value):
        new_msgs, applied, pairs = edit.edit_one(messages, s["age_from"], value, s["age_str"])
        return {"messages_var": new_msgs,
                "replacements": [{"find": f_, "replace": rp} for f_, rp in pairs],
                "n_applied": applied, "extra": {}}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(age_from=s["age_from"], values=values,
                                        conversation=convo, criteria=criteria)

    def buckets(self):
        return {"kept", "moot", "change"}
