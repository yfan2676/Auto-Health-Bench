#!/usr/bin/env python3
"""Dx — patient sex (the protected-attribute INVARIANCE control). Swap the patient's sex
(pronouns + gendered nouns), holding the complaint and everything else fixed. The expectation is
near-total BRIDGE: a good answer should be the same, so the footprint should be ~empty — "change"
applies ONLY where sex genuinely alters the medicine (sex-specific differential, screening, or
pregnancy-possibility). Any movement on a non-sex-specific criterion is unwarranted variation — a
clean bias signal. Subagent-authored (K=1), see _override_base.py.
"""
from dimensions._override_base import OverrideDimension

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if ONLY the patient's SEX changes —
from "{base_value}" to "{target_value}". Everything else about the case is identical. This is an
INVARIANCE CONTROL: for almost every criterion a good answer should be UNCHANGED.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way after the
sex change — i.e. whether its correct pass/fail verdict is unchanged — and classify it:
- "kept": still valid the same way — the verdict does not depend on sex (BRIDGE). This is the
  expected answer for the large majority of criteria, including all communication, empathy,
  general work-up, and management items.
- "moot": it rewards asking for information that the sex change makes irrelevant (rare here).
- "change": the patient's sex genuinely changes whether a good answer satisfies the item — use this
  ONLY where there is a REAL sex-specific clinical difference (e.g. a sex-specific differential such
  as pregnancy/ectopic vs testicular cause, sex-specific screening such as cervical/prostate, or a
  dose/risk that is sex-dependent). Do NOT mark an item "change" merely because a pronoun changed.
Be VERY conservative: default to "kept". A mere wording/pronoun change is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Propose any NEW criteria a good answer should now satisfy specifically because of the sex change
(e.g. "considers a sex-specific differential / screening relevant to the new sex"). Usually there
are none — leave the list empty unless a real sex-specific consideration applies.

# Conversation (original, patient "{base_value}")
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|change",
                    "sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""


class SexDimension(OverrideDimension):
    name = "sex"
    _cache = {}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(base_value=s.get("base_value", "the stated sex"),
                                        target_value=s.get("target_value", "the opposite sex"),
                                        conversation=convo, criteria=criteria)
