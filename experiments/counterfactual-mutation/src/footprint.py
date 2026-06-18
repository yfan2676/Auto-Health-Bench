#!/usr/bin/env python3
"""Step 3 — predict the rubric footprint of the dimension edit, a priori (before any model runs).

For each existing rubric criterion we predict whether the dimension edit changes that
criterion's correct verdict, and if so how (the dimension's bucket vocabulary). This is the
counterfactual-locality prediction the experiment then *tests* (src/sweep_grade.py +
src/analyze.py): predicted-`kept` criteria form the bridge (should not move); the rest form
the footprint (should move). Proposed *induced* criteria (newly warranted by the edit) are
recorded for the later mutation step.

This is the *a-priori* (LLM) estimate and only as trustworthy as the model — a 2-item Qwen3-4B
run predicted 0/22 sensitive for age, which is why the behavioral SWEEP (sweep_grade.py) is
the ground truth and analyze.py scores this classifier against it.

The prompt + allowed buckets come from the dimension (src/dimensions/), so this step is
dimension-agnostic.

Output: results/footprint/<example_id>.json
    {example_id, dimension, base_value, values,
     predictions: [{idx, bucket, predicted_sensitive, reason}],
     proposed_induced: ["...", ...]}
Resumable: skips items already classified.

Usage:
    python3 src/footprint.py            # classify every shortlisted item
    python3 src/footprint.py --limit 2
"""
import argparse
import json
import os

import common
import dimensions

# Per-endpoint concurrency for the (long, thinking-on) footprint author calls. Smaller than the
# grading default because each generation is heavy; len(JUDGE_EPS) * this many run at once.
CM_AUTHOR_CONCURRENCY = int(os.environ.get("CM_AUTHOR_CONCURRENCY", "4"))


def classify(dim, ex, s, values, endpoint=None):
    prompt = dim.footprint_prompt(ex, s, values)
    try:
        obj = common.author_json(prompt, endpoint=endpoint)
    except RuntimeError:
        # The thinking trace on a long rubric list can exceed HB_MAX_TOKENS; retry without
        # thinking so the run doesn't crash (raise HB_MAX_TOKENS=16384 for better predictions).
        obj = common.author_json(prompt, think=False, endpoint=endpoint)
    allowed = dim.buckets()
    preds = {}
    for p in obj.get("predictions", []):
        try:
            idx = int(p["idx"])
        except (KeyError, ValueError, TypeError):
            continue
        bucket = p.get("bucket", "kept")
        if bucket not in allowed:
            bucket = "kept"
        sensitive = bool(p.get("sensitive", p.get("predicted_sensitive", bucket != "kept")))
        preds[idx] = {"idx": idx, "bucket": bucket, "predicted_sensitive": sensitive,
                      "reason": p.get("reason", "")}
    # Any criterion the model omitted defaults to kept (conservative).
    for r in ex["rubrics"]:
        preds.setdefault(r["idx"], {"idx": r["idx"], "bucket": "kept",
                                    "predicted_sensitive": False, "reason": "(unclassified -> kept)"})
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

    # Resume: count already-classified items, queue only the missing ones. The author calls are
    # independent, so we fan them across every judge endpoint (GPU) with common.pmap instead of
    # the old one-at-a-time loop.
    skipped = 0
    n_sensitive = n_total = 0
    todo = []
    for s in shortlist:
        out = common.FOOTPRINT / f"{s['example_id']}.json"
        if out.exists():
            skipped += 1
            rec = json.loads(out.read_text())
            n_sensitive += sum(p["predicted_sensitive"] for p in rec["predictions"])
            n_total += len(rec["predictions"])
            continue
        ex = by_id.get(s["example_id"])
        if not ex:
            print(f"skip {s['example_id']}: not found in split")
            continue
        todo.append((s, ex))

    def work(item, ep):
        s, ex = item
        dim = dimensions.get(s.get("dimension", "age"))
        values = dim.values(s)
        preds, induced = classify(dim, ex, s, values, endpoint=ep)
        return values, preds, induced

    workers = max(1, len(common.JUDGE_EPS) * CM_AUTHOR_CONCURRENCY)
    print(f"classifying {len(todo)} missing items across {len(common.JUDGE_EPS)} endpoint(s), "
          f"{workers} workers ({len(shortlist) - len(todo)} already done)")
    results = common.pmap(work, todo, workers=workers)

    done = errored = 0
    for (s, _ex), res in zip(todo, results):
        if isinstance(res, Exception):
            print(f"  ! {s['example_id']}: footprint error ({type(res).__name__}: {res}); "
                  f"will retry on resume")
            errored += 1
            continue
        values, preds, induced = res
        out = common.FOOTPRINT / f"{s['example_id']}.json"
        common.atomic_write_json(out, {
            "example_id": s["example_id"], "dimension": s.get("dimension", "age"),
            "base_value": s.get("base_value", s.get("age_from")), "values": values,
            "predictions": preds, "proposed_induced": induced,
        })
        sens = sum(p["predicted_sensitive"] for p in preds)
        n_sensitive += sens
        n_total += len(preds)
        done += 1
        print(f"[{done}/{len(todo)}] {s['example_id']}  ({s.get('dimension','age')})  "
              f"{sens}/{len(preds)} criteria predicted sensitive; +{len(induced)} induced")

    frac = (n_sensitive / n_total) if n_total else 0.0
    print(f"done: classified {done}, skipped {skipped}, errored {errored}. "
          f"Predicted footprint = {n_sensitive}/{n_total} criteria ({frac:.1%}) -> {common.FOOTPRINT}/")


if __name__ == "__main__":
    main()
