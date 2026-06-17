#!/usr/bin/env python3
"""The deterministic AGE-edit primitive (used by dimensions/age.py).

Editing the patient's age must be MINIMAL: change only the age and the words it directly
entails, leaving all clinical content byte-for-byte intact. Rather than ask the model to echo
back the whole (possibly long) conversation — fragile for small models, and prone to silently
dropping content — we use a robust find/replace design:

  1. a DETERMINISTIC primary swap of the detected age string (e.g. "39 year old" -> "72
     year old"), applied in Python, and
  2. small, optional LLM-suggested EXTRA literal replacements (other age mentions, entailed
     life-stage words), each verified to be an exact substring before being applied.

This is minimal by construction (only listed spans change) and length-independent.
`edit_one` returns (messages_var, n_applied, pairs); `dimensions/age.py` wraps it for the
sweep, which applies the character-diff guard and writes the per-item sweep file.
"""
import re

import common

EDIT_PROMPT = """\
You are creating a counterfactual version of a medical conversation that changes exactly
ONE variable: the patient's age, from {age_from} to {age_to} years old.

The primary age mention ("{age_str}") is already being changed for you. List any ADDITIONAL
literal text replacements needed so the conversation is internally consistent at age
{age_to}: other age mentions, or words the age directly entails (life-stage nouns like
"teenager"/"toddler"/"elderly", school/retirement references that are purely age markers,
age-tied relations). Do NOT change symptoms, history, medications, durations, the chief
complaint, the tone, or the question asked. If nothing else needs changing, return [].

Each "find" MUST be an exact substring of the conversation below; keep spans short and
specific so nothing unintended matches.

# Conversation
{conversation}

Return ONLY JSON (no prose):
{{"replacements": [{{"find": "<exact substring>", "replace": "<new text>"}}]}}
"""


def _swap_number(s, age_from, age_to):
    """Replace the age number inside a detected age string, e.g. '39-year-old' -> '72-year-old'."""
    new = re.sub(rf"\b{age_from}\b", str(age_to), s, count=1)
    return new if new != s else s.replace(str(age_from), str(age_to), 1)


def _apply(messages, pairs):
    """Apply literal (find, replace) pairs across all message contents. Returns (new, n_applied)."""
    out, applied = [], 0
    for m in messages:
        c = m.get("content", "")
        for find, rep in pairs:
            if find and find in c and find != rep:
                applied += c.count(find)
                c = c.replace(find, rep)
        out.append({**m, "content": c})
    return out, applied


def edit_one(messages, age_from, age_to, age_str):
    # 1. deterministic primary swap of the detected age mention
    pairs = [(age_str, _swap_number(age_str, age_from, age_to))]
    # 2. optional LLM-suggested extras (best-effort; primary edit stands even if this fails)
    try:
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        obj = common.author_json(EDIT_PROMPT.format(
            age_from=age_from, age_to=age_to, age_str=age_str, conversation=convo))
        for r in obj.get("replacements", []):
            f_, rp = (r.get("find") or "").strip(), (r.get("replace") or "")
            if f_ and (f_, rp) not in pairs:
                pairs.append((f_, rp))
    except Exception as e:  # noqa: BLE001 — extras are optional
        print(f"  (note: LLM extras skipped: {type(e).__name__}: {e})")
    new_msgs, applied = _apply(messages, pairs)
    return new_msgs, applied, pairs
