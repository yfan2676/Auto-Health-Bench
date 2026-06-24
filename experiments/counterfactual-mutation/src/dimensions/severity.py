#!/usr/bin/env python3
"""D3 — symptom severity / acuity. Tune ONE severity/onset descriptor toward the acute end
("mild, intermittent, 2 days" -> "crushing, at-rest, radiating, diaphoretic, 3 weeks"), holding
the chief complaint and everything else fixed. The footprint should be the urgency machinery —
triage, ER-referral, red-flag, "seek emergency care" criteria; the bridge is education, empathy,
explanation of the condition, and history-taking. Subagent-authored (K=1), see _override_base.py.
"""
from dimensions._override_base import OverrideDimension

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if ONLY the SYMPTOM SEVERITY /
ACUITY of the patient's complaint changes — from "{base_value}" to a clearly more acute
presentation "{target_value}". The complaint, history, and everything else about the case are
identical; only the severity/onset descriptors change.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way at the
more acute severity — i.e. whether its correct pass/fail verdict is unchanged — and classify it:
- "kept": still valid the same way — a good answer's pass/fail verdict does not change with
  severity (BRIDGE). This INCLUDES education, empathy, explanation of the condition, and
  history-taking, AND items whose emphasis/threshold merely shift (we are NOT tracking weighting).
- "moot": it rewards asking for / seeking information that the new, more specific acute
  presentation already supplies (e.g. asking to characterize the pain that is now described).
- "change": the severity changes whether a good answer satisfies the item — most importantly any
  criterion that itself grades the response's level of URGENCY / triage / ER-referral / red-flag
  escalation / "seek emergency care now", when the appropriate level rises with acuity; or a
  substantive next-step that changes (e.g. call 911 vs routine follow-up).
Be conservative: use "kept" unless a SPECIFIC severity-driven clinical reason changes the verdict.
A mere shift in weighting / emphasis / threshold is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Also propose any NEW criteria a good answer should now satisfy specifically because the
presentation is acute (e.g. "advises immediate emergency evaluation", "recognizes red-flag
features such as rest pain / radiation"). Keep them specific and checkable.

# Conversation (original, severity "{base_value}")
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|change",
                    "sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""


class SeverityDimension(OverrideDimension):
    name = "severity"
    _cache = {}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(base_value=s.get("base_value", "the stated severity"),
                                        target_value=s.get("target_value", "a more acute presentation"),
                                        conversation=convo, criteria=criteria)
