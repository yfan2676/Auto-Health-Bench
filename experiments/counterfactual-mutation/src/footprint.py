#!/usr/bin/env python3
"""Step 3 — predict the rubric footprint of the age edit, a priori (before any model runs).

For each existing rubric criterion we predict whether changing the patient's age from
`age_from` to `age_to` changes that criterion's correct verdict, and if so how. This is the
counterfactual-locality prediction the experiment then *tests* (src/paired_grade.py +
src/analyze.py): predicted-`kept` criteria form the bridge (should not move); the rest form
the footprint (should move). We also collect proposed *induced* criteria the older/younger
case newly warrants — not used for the V1/V2 verdict test, but recorded for the later
mutation step.

This is the *a-priori* (LLM) footprint estimate and is only as trustworthy as the model.
The stronger, second estimator is behavioral — sweep the age over several values and see
which verdicts actually move (idea doc §4.1; experiment E1b / sweep.py). Use the measured
footprint as ground truth and score this classifier against it.

Buckets per existing criterion (mirrors the data-axis change-types, keyed to age):
  kept          — age-neutral; correct verdict unchanged  (BRIDGE)
  moot          — rewards asking/seeking something the age now makes irrelevant
  reweight      — still relevant but its threshold/strength changes with age
  urgency       — age changes the appropriate triage / red-flag level
  answer_shift  — age changes the substantive recommendation (differential, dose, screening)

Output: results/footprint/<example_id>.json
    {example_id, age_from, age_to,
     predictions: [{idx, bucket, age_sensitive, reason}],
     proposed_induced: ["new criterion the edited age warrants", ...]}
Resumable: skips items already classified.

Usage:
    python3 src/footprint.py            # classify every shortlisted item
    python3 src/footprint.py --limit 5
"""
import argparse
import json

import common

FOOTPRINT_PROMPT = """\
You are auditing how a medical grading rubric should change if ONLY the patient's age
changes, from {age_from} to {age_to} years old. Everything else about the case is identical.

For EACH numbered criterion, decide whether the criterion's correct pass/fail verdict for a
good answer would change at age {age_to} versus age {age_from}, and classify it:
- "kept": age-neutral — a good answer satisfies it the same way at both ages.
- "moot": it rewards asking for / seeking information that the new age makes irrelevant.
- "reweight": still relevant but its threshold, strength, or expected detail changes with age.
- "urgency": the age changes the appropriate level of triage / red-flag / referral.
- "answer_shift": the age changes the substantive recommendation (differential, dose,
  screening, contraindication).
Be conservative: use "kept" unless a SPECIFIC age-driven clinical reason makes it change.
Set "age_sensitive" true for everything that is not "kept".

Also propose any NEW criteria a good answer should now satisfy specifically because of the
age change (e.g. geriatric falls/polypharmacy at an older age; growth/development or
guardian involvement at a younger age). Keep them specific and checkable.

# Conversation (original, age {age_from})
{conversation}

# Criteria (numbered by idx)
{criteria}

Return ONLY this JSON (no prose):
{{"predictions": [{{"idx": <int>, "bucket": "kept|moot|reweight|urgency|answer_shift",
                    "age_sensitive": <bool>, "reason": "<one clause>"}}],
  "proposed_induced": ["<new criterion>", "..."]}}
Every idx in the criteria list must appear exactly once in predictions.
"""

_BUCKETS = {"kept", "moot", "reweight", "urgency", "answer_shift"}


def classify(ex, age_from, age_to):
    convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
    criteria = "\n".join(f"[idx {r['idx']}] ({r['points']:+d}, {r['axis']}) {r['criterion']}"
                         for r in ex["rubrics"])
    prompt = FOOTPRINT_PROMPT.format(age_from=age_from, age_to=age_to,
                                     conversation=convo, criteria=criteria)
    obj = common.author_json(prompt)
    preds = {}
    for p in obj.get("predictions", []):
        idx = int(p["idx"])
        bucket = p.get("bucket", "kept")
        if bucket not in _BUCKETS:
            bucket = "kept"
        preds[idx] = {"idx": idx, "bucket": bucket,
                      "age_sensitive": bool(p.get("age_sensitive", bucket != "kept")),
                      "reason": p.get("reason", "")}
    # Any criterion the model omitted defaults to kept (conservative).
    for r in ex["rubrics"]:
        preds.setdefault(r["idx"], {"idx": r["idx"], "bucket": "kept",
                                    "age_sensitive": False, "reason": "(unclassified -> kept)"})
    return [preds[r["idx"]] for r in ex["rubrics"]], obj.get("proposed_induced", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.FOOTPRINT.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(footprint)", len(shortlist))

    done = skipped = 0
    n_sensitive = n_total = 0
    for s in shortlist:
        out = common.FOOTPRINT / f"{s['example_id']}.json"
        if out.exists():
            skipped += 1
            rec = json.loads(out.read_text())
            n_sensitive += sum(p["age_sensitive"] for p in rec["predictions"])
            n_total += len(rec["predictions"])
            continue
        ex = by_id.get(s["example_id"])
        if not ex:
            print(f"skip {s['example_id']}: not found in split")
            continue
        preds, induced = classify(ex, s["age_from"], s["target_age"])
        common.atomic_write_json(out, {
            "example_id": s["example_id"], "age_from": s["age_from"], "age_to": s["target_age"],
            "predictions": preds, "proposed_induced": induced,
        })
        sens = sum(p["age_sensitive"] for p in preds)
        n_sensitive += sens
        n_total += len(preds)
        done += 1
        print(f"[{done}] {s['example_id']}  {sens}/{len(preds)} criteria predicted age-sensitive; "
              f"+{len(induced)} induced")

    frac = (n_sensitive / n_total) if n_total else 0.0
    print(f"done: classified {done}, skipped {skipped}. "
          f"Predicted footprint = {n_sensitive}/{n_total} criteria ({frac:.1%}) -> {common.FOOTPRINT}/")


if __name__ == "__main__":
    main()
