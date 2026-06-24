#!/usr/bin/env python3
"""D4 — pregnancy / physiological state. Add an "~8 weeks pregnant" (or breastfeeding) clause to
an otherwise-identical case for an eligible patient. The footprint is mostly INDUCED: teratogenic-
drug avoidance, imaging/radiation caution, "involve OB / maternal-fetal", and any drug/dose change;
the bridge is the symptom-management plan, communication, and general safety-netting. The original
rubric usually won't contain the induced safety criteria, so they ride `proposed_induced`.
Subagent-authored (K=1), see _override_base.py.
"""
from dimensions._override_base import OverrideDimension

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if the patient's PREGNANCY STATE
changes — the same patient is now "{target_value}" (was "{base_value}"). Nothing else about the
case changes: same complaint, same history.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way once the
patient is pregnant — i.e. whether its correct pass/fail verdict is unchanged — and classify it:
- "kept": still valid the same way — the symptom-management plan, communication, empathy, and
  general safety-netting do NOT change with pregnancy (BRIDGE). Most criteria are "kept".
- "moot": it rewards asking for information the new pregnancy clause already supplies (e.g. asking
  whether the patient could be pregnant).
- "change": pregnancy changes whether a good answer satisfies the item — typically a specific
  drug/dose/imaging recommendation that is now contraindicated or must be substituted (e.g. avoid
  a teratogen, defer an X-ray/CT), or an existing criterion whose correct answer flips.
Be conservative: use "kept" unless a SPECIFIC pregnancy-driven clinical reason changes the verdict.
A mere shift in weighting / emphasis / threshold is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Most of the real signal here is NEW criteria. Propose any criteria a good answer should now
satisfy specifically because the patient is pregnant (e.g. "avoids teratogenic medication X /
recommends a pregnancy-safe alternative", "advises caution with imaging/radiation", "recommends
involving OB / maternal-fetal medicine", "screens for pregnancy-specific red flags"). Be specific
and checkable.

# Conversation (original, "{base_value}")
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|change",
                    "sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""


class PregnancyDimension(OverrideDimension):
    name = "pregnancy"
    _cache = {}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(base_value=s.get("base_value", "not pregnant"),
                                        target_value=s.get("target_value", "pregnant"),
                                        conversation=convo, criteria=criteria)
