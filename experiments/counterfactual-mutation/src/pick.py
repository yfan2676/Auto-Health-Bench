#!/usr/bin/env python3
"""Step 1 — select HealthBench items that state a patient age (the D1 dimension).

We pick conversations that mention an explicit age in years, since age is the cheapest
dimension to mutate (a pure text edit, no data synthesis) and exposes a rich, plausibly
*local* rubric footprint. Whether an item actually has age-sensitive criteria is decided
later by the footprint classifier (src/footprint.py); selection only guarantees there is
an age to edit. The complementary `target_age` is chosen to land in a clearly different
life-stage so the counterfactual is meaningful.

Output: results/shortlist.jsonl, one object per selected item:
    {example_id, age_from, age_str, target_age, n_rubrics, axes:{axis:count}}

Usage:
    python3 src/pick.py --split full --limit 30      # first N age-stating items (0 = all)
    python3 src/pick.py --split full --limit 0 --target-age 70
"""
import argparse
import json
import re
from collections import Counter

import common

# Conservative year-age patterns. We avoid bare "I'm 34" (too many false positives) and
# month/week-old infants (a different life-stage-edit problem), keeping E1 clean.
_AGE_PATTERNS = [
    re.compile(r"\b(\d{1,3})[\s-]*(?:years?|yrs?)[\s-]*old\b", re.I),
    re.compile(r"\b(\d{1,3})\s*[- ]?(?:yo|y/o|y\.o\.)\b", re.I),
    re.compile(r"\bage[d]?\s*(?:of|is|:)?\s*(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})[- ]year[- ]old\b", re.I),
]


def detect_age(messages):
    """Return (age:int, matched_str) for the first plausible year-age in the user text, else None."""
    text = "\n".join(m.get("content", "") for m in messages if m.get("role") != "assistant")
    for pat in _AGE_PATTERNS:
        for m in pat.finditer(text):
            age = int(m.group(1))
            if 0 < age <= 120:
                return age, m.group(0).strip()
    return None


def pick_target(age, forced=None):
    """Contrast age in a different life-stage (overridable with --target-age)."""
    if forced:
        return forced
    if age < 18:
        return 45          # child -> middle-aged adult
    if age < 50:
        return 72          # young/mid adult -> elderly (introduces geriatric considerations)
    return 28              # older adult -> young adult (removes them)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=30, help="keep first N age-stating items (0 = all)")
    ap.add_argument("--scan", type=int, default=0, help="scan only the first N examples (0 = all)")
    ap.add_argument("--target-age", type=int, default=None, help="force a single target age")
    args = ap.parse_args()

    examples = common.load_split(args.split, args.scan or None)
    common.RESULTS.mkdir(parents=True, exist_ok=True)

    selected = []
    for ex in examples:
        hit = detect_age(ex["messages"])
        if not hit:
            continue
        age, age_str = hit
        axes = Counter(r["axis"] for r in ex["rubrics"] if r["axis"])
        selected.append({
            "example_id": ex["example_id"],
            "age_from": age,
            "age_str": age_str,
            "target_age": pick_target(age, args.target_age),
            "n_rubrics": len(ex["rubrics"]),
            "axes": dict(axes),
        })
        if args.limit and len(selected) >= args.limit:
            break

    with common.SHORTLIST.open("w") as f:
        for s in selected:
            f.write(json.dumps(s) + "\n")

    scanned = len(examples)
    print(f"scanned {scanned} examples; selected {len(selected)} that state an age -> {common.SHORTLIST}")
    if selected:
        ages = [s["age_from"] for s in selected]
        print(f"age range {min(ages)}-{max(ages)}; example: id={selected[0]['example_id']} "
              f"age {selected[0]['age_from']} ('{selected[0]['age_str']}') -> {selected[0]['target_age']}")


if __name__ == "__main__":
    main()
