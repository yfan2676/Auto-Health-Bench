#!/usr/bin/env python3
"""Shared base for the K=1, subagent-authored dimensions (D3 severity, D4 pregnancy,
D5 comorbidity, Dx sex).

Unlike D1 (regex age-swap) and D2 (regex prefilter + LLM/subagent render), these dimensions
are too semantic to detect by regex — pregnancy needs an eligible patient, comorbidity ADDS
something absent, severity tunes a descriptor, sex swaps gendered tokens. So a capable Claude
subagent both DECIDES applicability and AUTHORS the single edit, writing one override file per
item under results/edits_override/<dimension>/<eid>.json. This class just loads that file and
applies its deterministic exact-substring edits — the same trust model as D2's overrides
(extra.source="subagent", so sweep.py's char-diff guard is advisory).

The "sweep" here is degenerate: K=1 (one mutated state per item), so values() returns a single
element. Everything downstream (sweep.py, answers.py, sweep_grade.py, analyze.py, the viewer)
is dimension-agnostic and works off the shortlist `dimension` field unchanged.

Override schema (per item):
    {"example_id", "dimension", "applicable": <bool>,
     "base_value": "<original-state label>", "target_value": "<mutated-state label>",
     "label": "<variant label>",
     "edits": [{"find": "<exact substring of one USER message>", "replace": "<new text>"}],
     "rationale": "<one clause>", "note": "<optional caveat>"}
An insertion is expressed as a replace whose `find` is an existing clause and `replace` re-emits
that clause plus the added phrase, so the apply path stays a pure str.replace(find, repl, 1).
"""
import json

import common
from dimensions.base import Dimension


def _user_text(messages):
    return "\n".join(m.get("content", "") for m in messages if m.get("role") != "assistant")


class OverrideDimension(Dimension):
    name = "override-base"  # subclasses set this; each also sets its own `_cache = {}`
    _cache = {}

    def _load_override(self, eid):
        key = (self.name, eid)
        if key in self._cache:
            return self._cache[key]
        path = common.override_path(self.name, eid)
        obj = None
        if path.exists():
            try:
                obj = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                obj = None
        self._cache[key] = obj
        return obj

    def detect(self, ex):
        """Detection IS the subagent's `applicable` flag: return a shortlist row only when an
        applicable override exists. Lets pick.py drive this dimension too, though the normal
        path is materialize_shortlist.py building rows straight from the override files."""
        ov = self._load_override(ex["example_id"])
        if not ov or not ov.get("applicable"):
            return None
        return {"dimension": self.name, "base_value": ov.get("base_value"),
                "target_value": ov.get("target_value"), "label": ov.get("label", self.name)}

    def values(self, s):
        """K=1: a single mutated state (the override's target_value)."""
        ov = self._load_override(s["example_id"]) or {}
        return [ov.get("target_value", s.get("target_value", "mutated"))]

    def edit_one(self, messages, s, value):
        ov = self._load_override(s["example_id"]) or {}
        edits = [(e["find"], e["replace"]) for e in ov.get("edits", [])
                 if e.get("find") and "replace" in e]
        new_msgs, applied = [], 0
        for m in messages:
            c = m.get("content", "")
            for find, rep in edits:
                if find and find in c:
                    c = c.replace(find, rep, 1)
                    applied += 1
            new_msgs.append({**m, "content": c})
        return {"messages_var": new_msgs,
                "replacements": [{"find": f_, "replace": rp} for f_, rp in edits],
                "n_applied": applied,
                "extra": {"source": "subagent", "fact_preserved": True,
                          "base_value": ov.get("base_value"), "target_value": value,
                          "rationale": ov.get("rationale", ""), "note": ov.get("note", "")}}

    def buckets(self):
        # Induced D4/D5 criteria (teratogen avoidance, interaction warnings) ride the footprint
        # JSON's existing `proposed_induced` list, so the bucket vocabulary stays identical to D1/D2.
        return {"kept", "moot", "change"}
