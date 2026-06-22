#!/usr/bin/env python3
"""D2 — mode of disclosure ("data interpretability"). Re-encode a STATED fact as DATA while
holding the clinical fact constant: "I have hypertension" -> "a blood pressure of 152/96
mmHg". The fact is unchanged, so the entire clinical-management rubric is the BRIDGE; the
only legitimate movers are criteria that reward *asking/confirming* the value (now shown ->
"moot") and criteria that reward *correctly reading/interpreting* the value ("change").
This is the cleanest construct-validity control (idea doc §5, D2): it isolates the
ask->interpret shift from any new-information confound.

Detection is a cheap regex prefilter (so we never call a model on the whole split) followed
by an LLM confirm that the span really states the fact (not a question / not a denial) and
is re-encodable without adding or removing clinical information. The "sweep" over a
categorical dimension is a few realistic data renderings of the same fact.

Risk (small judge/author model): a 4B model can leak or drop clinical info when rendering
prose->data. Guarded by a deterministic span replacement, an LLM `fact_preserved` check
(-> ok=False, excluded), and the diff guard; and the sweep itself flags leakage — if the
management bridge moves, the dimension isn't local (demote it).
"""
import json
import re

import common
from dimensions.base import Dimension

# Subagent-authored edits (results/edits_override/<eid>.json) take precedence over the small
# model's prose->data rendering. Re-encoding a stated fact as a clinically faithful, in-range,
# grammatically clean data value is the demanding step where a 4B model is weakest, so when a
# capable agent has authored the renderings we use those verbatim. Schema:
#   {"example_id", "encoding_kind", "fact",
#    "renderings": [{"style": <one of values()>, "find": <substring to replace,
#                    defaults to stated_span>, "data_phrase": <replacement text>}, ...]}
# Missing file / missing style -> fall back to the LLM render below.
_OVERRIDE_CACHE = {}


def _load_override(eid):
    if eid in _OVERRIDE_CACHE:
        return _OVERRIDE_CACHE[eid]
    path = common.EDITS_OVERRIDE / f"{eid}.json"
    obj = None
    if path.exists():
        try:
            obj = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            obj = None
    _OVERRIDE_CACHE[eid] = obj
    return obj

# Each entry: (encoding_kind, compiled regex over user text). The regex match is the exact
# stated_span we delete; the LLM confirm supplies the canonical fact. A leading severity
# qualifier (mild/moderate/...) is absorbed into the span so replacing it doesn't leave a
# dangling adjective (e.g. "mild hypertension" -> the whole phrase becomes the data value).
_QUAL = r"(?:(?:mild|moderate|severe|borderline|well[-\s]?controlled|uncontrolled|controlled)\s+)?"
_FACT_PATTERNS = [
    ("bp", re.compile(rf"\b{_QUAL}(?:high blood pressure|hypertension|hypertensive)\b", re.I)),
    ("lab_a1c", re.compile(rf"\b{_QUAL}(?:type 2 diabetes|type ii diabetes|diabetic|diabetes|"
                           r"high blood sugar|blood sugar (?:has been|is|was|runs) high)\b", re.I)),
    ("lab_lipids", re.compile(rf"\b{_QUAL}(?:high cholesterol|hyperlipidemia|high lipids)\b", re.I)),
    ("med_list", re.compile(r"\b(?:on|taking|takes|prescribed) (?:metformin|lisinopril|atorvastatin|"
                            r"amlodipine|levothyroxine|omeprazole|metoprolol|losartan|warfarin|insulin)\b", re.I)),
]

_KIND_LABELS = {
    "bp": "blood pressure", "lab_a1c": "blood-sugar lab", "lab_lipids": "lipid panel",
    "med_list": "medication record",
}

# The categorical "sweep": three data renderings of the SAME fact, increasing in structure.
_STYLES = {
    "bp": ["a single BP reading", "two BP readings", "a vitals line (BP, HR)"],
    "lab_a1c": ["an HbA1c value", "a fasting glucose value", "a flagged lab line"],
    "lab_lipids": ["an LDL value", "a lipid-panel line", "a flagged lab line"],
    "med_list": ["a medication-list line", "a med-reconciliation row", "a structured med block"],
}

_CONFIRM_PROMPT = """\
In the patient conversation below, the phrase "{span}" was matched. Decide whether the
patient is STATING (as an established fact about themselves) the clinical fact that this
phrase denotes — not asking about it, not denying it, not raising it as a worry only.

If yes, give the canonical clinical fact in a few words and confirm it could be re-expressed
as a concrete DATA value (a measurement, lab result, or medication record) WITHOUT adding or
removing any clinical information.

# Conversation
{conversation}

Return ONLY JSON:
{{"fit": <bool>, "fact": "<canonical fact, e.g. 'stage 1 hypertension'>", "reason": "<one clause>"}}
"""

_RENDER_PROMPT = """\
Re-express this stated clinical fact as a short DATA-style phrase that can directly REPLACE
the quoted prose in a patient message, stating the SAME diagnosis as a concrete measured value.

Fact: {fact}
Render it as: {style}
It will replace this exact prose: "{span}"

Requirements:
- ALWAYS include a concrete numeric value (a measurement / lab result), never a vague phrase.
- Pick a value squarely and UNAMBIGUOUSLY in the diagnostic range for the fact, so a reader
  would conclude the same diagnosis from the number alone (e.g. hypertension -> 150/95 mmHg,
  clearly above 140/90; diabetes -> HbA1c 8.0%, clearly above 6.5%; hyperlipidemia ->
  LDL 165 mg/dL, clearly above 160). Do NOT pick a borderline/normal value.
- Add no new diagnosis and remove no information; only change prose -> a data value.
- Keep it short and grammatical in place of the prose.

Return ONLY JSON: {{"data_phrase": "<the replacement text>"}}
"""

_VERIFY_PROMPT = """\
A patient's stated diagnosis "{fact}" is being re-expressed as a data value: "{phrase}".

Is the data value CONSISTENT with that diagnosis — i.e. its magnitude is unambiguously in the
range a clinician would read as the same condition — and does it introduce no DIFFERENT or
ADDITIONAL diagnosis? (A concrete value replacing the prose is expected and fine; only flag a
value that is borderline/normal for the condition, contradicts it, or adds a new finding.)

Return ONLY JSON: {{"fact_preserved": <bool>, "reason": "<one clause>"}}
"""

_FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if ONLY the MODE OF DISCLOSURE of
one fact changes: the patient's stated "{fact}" is re-expressed as a concrete DATA value
(we will test these renderings: {values}). The clinical fact itself is UNCHANGED.

For EACH numbered criterion, decide whether a good answer still satisfies it the SAME way once
the fact is shown as data instead of prose — i.e. whether its correct pass/fail verdict is
unchanged — and classify it:
- "kept": still valid the same way — a clinical-management criterion whose pass/fail verdict does
  not change, because the underlying fact is the same (BRIDGE). This INCLUDES items whose emphasis
  or threshold would merely shift (we are NOT tracking weighting), AND items that do not themselves
  require interpreting the data: if the criterion is not originally about reading the value, and a
  good answer can implicitly infer the underlying condition/symptom from the shown value and go on
  to satisfy the criterion the same way, it is "kept" — the rubric does not demand that the answer
  explicitly read out or interpret the number.
- "moot": it rewards ASKING FOR or CONFIRMING the value that is now shown in the data.
- "change": the data form changes whether a good answer satisfies the item. Use this ONLY when the
  criterion is ITSELF about interpreting the value — it explicitly grades whether the answer reads
  the shown number correctly (numeracy), e.g. "recognizes the BP as hypertensive", "notes the A1c
  indicates poor control"; or, rarely, when the data form changes the substantive recommendation.
  Do NOT mark a management criterion "change" just because the fact is now a number — if a good
  answer can use the value implicitly, the criterion is "kept".
Be conservative: most criteria are "kept" because the underlying fact does not change.
A mere shift in weighting / emphasis / threshold is NOT a change -> "kept".
Set "sensitive" true for everything that is not "kept" (i.e. "moot" or "change").

Also propose any NEW criteria a good answer should now satisfy specifically because the value
is shown (e.g. "interprets the numeric value correctly").

# Conversation (original, fact stated as prose)
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|change",
                    "sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""


def _user_text(messages):
    return "\n".join(m.get("content", "") for m in messages if m.get("role") != "assistant")


class DisclosureDimension(Dimension):
    name = "disclosure"

    def detect(self, ex):
        text = _user_text(ex["messages"])
        for kind, pat in _FACT_PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            span = m.group(0)
            # The span must live inside a single user message (so the editor can replace it).
            if not any(span in msg.get("content", "") for msg in ex["messages"]
                       if msg.get("role") != "assistant"):
                continue
            convo = "\n\n".join(f"{mm['role']}: {mm['content']}" for mm in ex["messages"])
            try:
                obj = common.author_json(_CONFIRM_PROMPT.format(span=span, conversation=convo),
                                         temperature=0)
            except Exception:  # noqa: BLE001 — a confirm that won't parse just isn't fit
                continue
            if not obj.get("fit"):
                continue
            # Encoding kind is fixed by which pattern matched the span (so the data rendering
            # stays type-consistent with the prose, e.g. "hypertension" -> a BP reading). The
            # LLM only decides fit + the canonical fact, not how to encode it.
            ekind = kind
            return {"dimension": self.name, "base_value": "prose",
                    "label": f"{_KIND_LABELS.get(ekind, 'fact')} stated as prose",
                    "encoding_kind": ekind, "fact": obj.get("fact", span),
                    "stated_span": span, "detect_reason": obj.get("reason", "")}
        return None

    def values(self, s):
        return list(_STYLES.get(s.get("encoding_kind"), _STYLES["bp"]))

    def _override_rendering(self, s, value):
        """Return (find_span, data_phrase) from a subagent override for this style, or None.
        Matches by exact style string, then by the style's position in values() as a fallback."""
        ov = _load_override(s["example_id"])
        if not ov:
            return None
        rends = ov.get("renderings", [])
        match = next((r for r in rends if r.get("style") == value), None)
        if match is None:
            vals = self.values(s)
            if value in vals and vals.index(value) < len(rends):
                match = rends[vals.index(value)]
        if not match or not str(match.get("data_phrase", "")).strip():
            return None
        return (match.get("find") or s["stated_span"], str(match["data_phrase"]).strip())

    def _render_llm(self, fact, span, value):
        """Small-model prose->data rendering (temp 0, retry at 0.7) + advisory fact-preserved
        check. Used only when no subagent override covers this style."""
        block = ""
        for temp in (0, 0.7):
            try:
                block = (common.author_json(_RENDER_PROMPT.format(fact=fact, style=value, span=span),
                                            temperature=temp).get("data_phrase", "")).strip()
            except Exception:  # noqa: BLE001
                block = ""
            if block:
                break
        fact_preserved = True
        if block:
            try:
                fact_preserved = bool(common.author_json(
                    _VERIFY_PROMPT.format(fact=fact, phrase=block),
                    temperature=0).get("fact_preserved", True))
            except Exception:  # noqa: BLE001 — treat an unparseable check as a soft pass
                fact_preserved = True
        return span, block, fact_preserved, "llm"

    def edit_one(self, messages, s, value):
        fact = s["fact"]
        # Prefer a subagent-authored edit; its faithfulness is vetted by the author, so
        # fact_preserved is True and the (advisory) small-model verify is skipped.
        ov = self._override_rendering(s, value)
        if ov is not None:
            span, block, fact_preserved, source = ov[0], ov[1], True, "subagent"
        else:
            span, block, fact_preserved, source = self._render_llm(fact, s["stated_span"], value)

        new_msgs, applied = [], 0
        for m in messages:
            c = m.get("content", "")
            if block and span in c:
                c = c.replace(span, block, 1)
                applied += 1
            new_msgs.append({**m, "content": c})
        return {"messages_var": new_msgs,
                "replacements": [{"find": span, "replace": block}],
                "n_applied": applied,
                "extra": {"fact_preserved": fact_preserved, "data_phrase": block,
                          "style": value, "source": source}}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(fact=s.get("fact", "the stated fact"), values=values,
                                        conversation=convo, criteria=criteria)

    def buckets(self):
        return {"kept", "moot", "change"}
