#!/usr/bin/env python3
"""Step 6 — measure the same-input floor (so the off-target change rate is interpretable).

The off-target change rate compares the model's answer to V against its answer to each V_k.
Both are *independently sampled*, so some criteria would flip even with NO dimension change,
purely from the model's roll-to-roll answer variance. This step measures that baseline: for a
sample of items we regenerate K fresh answers to the SAME original input (thinking on, at the
target temperature) and grade each criterion against each. A criterion is "unstable" if its
verdict is not unanimous — measured reference-based (answer[0] vs the other K-1) to match the
off-target definition exactly (verdict to V vs verdict to each V_k). The honest dimension
signal is `net = off-target change rate − this floor`.

The floor is measured per dimension (it can differ — e.g. how numerically a fact is encoded
affects answer variance). `--dimension` restricts to one and merges into the existing file;
omit it to measure every dimension in the shortlist.

Output: results/noise_floor.json
    {k, judge_temp, judge_think, metric,
     by_dimension: {<dim>: {flip_rate, n_criteria, n_items, examples_used}}}

Usage:
    python3 src/noise_floor.py --k 4 --items 12 --max-criteria 12
    python3 src/noise_floor.py --dimension disclosure --k 4 --items 20
"""
import argparse
import json

import common

_METRIC = ("same-input answer-resampling flip rate: K fresh answers to the same input, "
           "reference-based (answer[0] vs the other K-1), any verdict differs")


def measure_dimension(rows, by_id, k, max_criteria):
    """Return (flip_rate, n_criteria, n_unstable, examples_used) for one dimension's items."""
    n_criteria = n_unstable = 0
    used = []
    for s in rows:
        eid = s["example_id"]
        ex = by_id.get(eid)
        if not ex:
            continue
        rubrics = ex["rubrics"][:max_criteria]
        # Regenerate K fresh answers to the SAME original input, fanned across the answer GPUs.
        answers = common.pmap(lambda _i, ep: common.target_answer(ex["messages"], endpoint=ep),
                              list(range(k)), endpoints=common.GEN_EPS)
        convos = [common.convo_string(ex["messages"], a)
                  for a in answers if not isinstance(a, Exception) and a]
        if len(convos) < 2:
            print(f"{eid}: skipped (only {len(convos)} fresh answers)")
            continue
        kk = len(convos)
        work = [(r, c) for r in rubrics for c in convos]
        results = common.pmap(lambda rc, ep: common.judge_criterion(rc[1], rc[0], endpoint=ep)[0], work)
        used.append(eid)
        for i, r in enumerate(rubrics):
            verdicts = [v for v in results[i * kk:(i + 1) * kk] if not isinstance(v, Exception)]
            if not verdicts:
                continue
            n_criteria += 1
            if any(v != verdicts[0] for v in verdicts[1:]):
                n_unstable += 1
        print(f"{eid}: sampled {len(rubrics)} criteria x{kk} fresh answers")
    flip_rate = (n_unstable / n_criteria) if n_criteria else 0.0
    return round(flip_rate, 4), n_criteria, n_unstable, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=4, help="fresh answers per item (reference + K-1 others)")
    ap.add_argument("--items", type=int, default=12, help="items sampled per dimension")
    ap.add_argument("--max-criteria", type=int, default=12, help="cap criteria per item")
    ap.add_argument("--dimension", default=None, help="restrict to one dimension (merges into the file)")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    dims = ([args.dimension] if args.dimension
            else sorted({s.get("dimension", "age") for s in shortlist}))
    common.RESULTS.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(noise_floor)", len(shortlist))

    out_p = common.RESULTS / "noise_floor.json"
    rec = json.loads(out_p.read_text()) if out_p.exists() else {}
    rec.update({"k": args.k, "judge_temp": common.CM_JUDGE_TEMP,
                "judge_think": common.CM_JUDGE_THINK, "metric": _METRIC})
    rec.setdefault("by_dimension", {})

    for dim in dims:
        rows = [s for s in shortlist if s.get("dimension", "age") == dim][:args.items]
        by_id = common.examples_by_id([s["example_id"] for s in rows])
        flip_rate, n_criteria, n_unstable, used = measure_dimension(
            rows, by_id, args.k, args.max_criteria)
        rec["by_dimension"][dim] = {"flip_rate": flip_rate, "n_criteria": n_criteria,
                                    "n_items": len(used), "examples_used": used}
        print(f"floor [{dim}]: {n_unstable}/{n_criteria} criteria unstable across k={args.k} "
              f"({flip_rate:.1%})")

    common.atomic_write_json(out_p, rec)
    print(f"-> {out_p}")


if __name__ == "__main__":
    main()
