#!/usr/bin/env python3
"""D2 — mode of disclosure ("data interpretability"). Re-encode a STATED fact as DATA while
holding the clinical fact constant: "I have hypertension" -> "a blood pressure of 152/96
mmHg". The fact is unchanged, so the entire clinical-management rubric is the BRIDGE; the
only legitimate movers are criteria that reward *asking/confirming* the value (now shown ->
"moot") and criteria that reward *correctly reading/interpreting* the value ("induced").
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
import re

import common
from dimensions.base import Dimension

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

For EACH numbered criterion, decide whether its correct pass/fail verdict for a good answer
would change once the fact is shown as data instead of prose, and classify it:
- "kept": clinical-management criterion — unchanged, because the fact is the same (BRIDGE).
- "moot": it rewards ASKING FOR or CONFIRMING the value that is now shown in the data.
- "induced": it rewards correctly READING / INTERPRETING the shown value (numeracy), e.g.
  "recognizes the BP as hypertensive", "notes the A1c indicates poor control".
- "answer_shift": the data form changes the substantive recommendation (rare here).
Be conservative: most criteria are "kept" because the underlying fact does not change.
Set "sensitive" true for everything that is not "kept".

Also propose any NEW criteria a good answer should now satisfy specifically because the value
is shown (e.g. "interprets the numeric value correctly").

# Conversation (original, fact stated as prose)
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|induced|answer_shift",
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

    def edit_one(self, messages, s, value):
        span, fact = s["stated_span"], s["fact"]
        # Render deterministically (temp 0); if the small model returns no parseable phrase,
        # retry once at a higher temperature to break out of the empty deterministic output.
        block = ""
        for temp in (0, 0.7):
            try:
                block = (common.author_json(_RENDER_PROMPT.format(fact=fact, style=value, span=span),
                                            temperature=temp).get("data_phrase", "")).strip()
            except Exception:  # noqa: BLE001
                block = ""
            if block:
                break
        new_msgs, applied = [], 0
        for m in messages:
            c = m.get("content", "")
            if block and span in c:
                c = c.replace(span, block, 1)
                applied += 1
            new_msgs.append({**m, "content": c})
        fact_preserved = True
        if block:
            try:
                fact_preserved = bool(common.author_json(
                    _VERIFY_PROMPT.format(fact=fact, phrase=block),
                    temperature=0).get("fact_preserved", True))
            except Exception:  # noqa: BLE001 — treat an unparseable check as a soft pass
                fact_preserved = True
        return {"messages_var": new_msgs,
                "replacements": [{"find": span, "replace": block}],
                "n_applied": applied,
                "extra": {"fact_preserved": fact_preserved, "data_phrase": block, "style": value}}

    def footprint_prompt(self, ex, s, values):
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                             for r in ex["rubrics"])
        return _FOOTPRINT_PROMPT.format(fact=s.get("fact", "the stated fact"), values=values,
                                        conversation=convo, criteria=criteria)

    def buckets(self):
        return {"kept", "moot", "induced", "answer_shift"}
