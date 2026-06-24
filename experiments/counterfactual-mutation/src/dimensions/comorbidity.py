#!/usr/bin/env python3
"""D5 — one comorbidity / medication. Add a SINGLE history item to an otherwise-identical case
("+ CKD", "+ on warfarin", "+ penicillin allergy"). The footprint is mostly INDUCED: an
interaction / contraindication / dose-adjustment for the primary plan (NSAID caution in CKD,
bleeding risk on warfarin, avoid the allergen); the bridge is the primary-complaint work-up and
advice. The original rubric usually won't contain the induced safety criteria, so they ride
`proposed_induced`. Subagent-authored (K=1), see _override_base.py.
"""
from dimensions._override_base import OverrideDimension

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if the patient now has ONE added
history item — "{target_value}" (the case was "{base_value}"). Nothing else changes: same chief
complaint, same presentation.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way given the
new comorbidity/medication/allergy — i.e. whether its correct pass/fail verdict is unchanged — and
classify it:
- "kept": still valid the same way — the primary-complaint work-up and advice do NOT change
  (BRIDGE). Most criteria are "kept".
- "moot": it rewards asking for information the new history item already supplies.
- "change": the added item changes whether a good answer satisfies the item — typically a specific
  drug/dose recommendation that is now contraindicated, interacts, or must be dose-adjusted, or an
  existing criterion whose correct answer flips because of the comorbidity.
Be conservative: use "kept" unless a SPECIFIC interaction/contraindication/dose reason changes the
verdict. A mere shift in weighting / emphasis / threshold is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Most of the real signal here is NEW criteria. Propose any criteria a good answer should now satisfy
specifically because of the added item (e.g. "avoids NSAIDs given CKD / adjusts renally-cleared
dosing", "warns about bleeding/INR interaction on warfarin", "avoids the penicillin-class agent and
chooses a safe alternative"). Be specific and checkable.

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


class ComorbidityDimension(OverrideDimension):
    name = "comorbidity"
    _cache = {}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(base_value=s.get("base_value", "no added comorbidity"),
                                        target_value=s.get("target_value", "an added comorbidity"),
                                        conversation=convo, criteria=criteria)
