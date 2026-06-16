#!/usr/bin/env python3
"""Step 2 — produce the age-edited conversation V' (the single-dimension counterfactual).

The edit must be MINIMAL: change only the patient's age and the words it directly entails,
leaving all clinical content byte-for-byte intact. Rather than ask the model to echo back
the whole (possibly long) conversation — fragile for small models, and prone to silently
dropping content — we use a robust find/replace design:

  1. a DETERMINISTIC primary swap of the detected age string (e.g. "39 year old" -> "72
     year old"), applied in Python, and
  2. small, optional LLM-suggested EXTRA literal replacements (other age mentions, entailed
     life-stage words), each verified to be an exact substring before being applied.

This is minimal by construction (only listed spans change) and length-independent. A
character-level diff guard still flags edits that change too much for manual review.

Output: results/variants/<example_id>.json
    {example_id, age_from, age_to, messages_orig, messages_var, replacements, n_applied,
     changed_chars, total_chars, change_frac, ok}
Resumable: skips items whose variant file already exists.

Usage:
    python3 src/edit.py            # edit every shortlisted item
    python3 src/edit.py --limit 5
"""
import argparse
import difflib
import json
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


def diff_chars(orig_msgs, new_msgs):
    """Characters changed between the original and edited conversations (insert/replace/delete)."""
    o = "\n".join(m.get("content", "") for m in orig_msgs)
    n = "\n".join(m.get("content", "") for m in new_msgs)
    sm = difflib.SequenceMatcher(a=o, b=n)
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return changed, max(len(o), len(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    ap.add_argument("--max-change-frac", type=float, default=0.25,
                    help="flag (ok=False) edits changing more than this fraction of characters")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.VARIANTS.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(edit)", len(shortlist))

    done = skipped = flagged = 0
    for s in shortlist:
        out = common.VARIANTS / f"{s['example_id']}.json"
        if out.exists():
            skipped += 1
            continue
        ex = by_id.get(s["example_id"])
        if not ex:
            print(f"skip {s['example_id']}: not found in split")
            continue
        new_msgs, applied, pairs = edit_one(ex["messages"], s["age_from"], s["target_age"], s["age_str"])
        changed, total = diff_chars(ex["messages"], new_msgs)
        frac = changed / total if total else 0.0
        ok = applied > 0 and frac <= args.max_change_frac   # must change the age, but not too much
        if not ok:
            flagged += 1
        common.atomic_write_json(out, {
            "example_id": s["example_id"],
            "age_from": s["age_from"], "age_to": s["target_age"],
            "messages_orig": ex["messages"], "messages_var": new_msgs,
            "replacements": [{"find": f_, "replace": rp} for f_, rp in pairs], "n_applied": applied,
            "changed_chars": changed, "total_chars": total, "change_frac": round(frac, 4),
            "ok": ok,
        })
        done += 1
        why = "" if ok else ("  FLAGGED:no-change" if applied == 0 else "  FLAGGED:large-diff")
        print(f"[{done}] {s['example_id']}  age {s['age_from']}->{s['target_age']}  "
              f"{applied} replacement(s), {changed}/{total} chars ({frac:.1%}){why}")

    print(f"done: edited {done}, skipped {skipped}, flagged {flagged} (no/large change) -> {common.VARIANTS}/")


if __name__ == "__main__":
    main()
