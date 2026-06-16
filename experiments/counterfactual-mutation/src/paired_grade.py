#!/usr/bin/env python3
"""Step 5 — the locality test (V1 bridge invariance + V2 on-target sensitivity).

For each item we take the FIXED answer to the original conversation and grade it twice,
per criterion, with the temperature-0 judge:
  - under the ORIGINAL conversation V   -> verdict_orig
  - under the age-EDITED conversation V' -> verdict_var   (same answer!)
A criterion's verdict "changed" iff verdict_orig != verdict_var. Because the answer is
identical, a change is caused by the age edit's effect on grading. Joined with the a-priori
footprint prediction (src/footprint.py), this yields:
  V1 (bridge): predicted-`kept` criteria should NOT change (off-target rate ~ judge noise).
  V2 (target): predicted-footprint criteria SHOULD change.

Output: results/grades/<example_id>.jsonl, one line per criterion:
    {idx, points, axis, predicted_bucket, age_sensitive, verdict_orig, verdict_var, changed}
Resumable: skips (item, idx) pairs already graded.

Usage:
    python3 src/paired_grade.py            # all items that have footprint + answer + variant
    python3 src/paired_grade.py --limit 5
"""
import argparse
import json

import common


def graded_idxs(path):
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["idx"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.GRADES.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(paired_grade)", len(shortlist))

    graded = 0
    for s in shortlist:
        eid = s["example_id"]
        var_p = common.VARIANTS / f"{eid}.json"
        fp_p = common.FOOTPRINT / f"{eid}.json"
        ans_p = common.ANSWERS / f"{eid}.json"
        if not (var_p.exists() and fp_p.exists() and ans_p.exists()):
            print(f"skip {eid}: needs edit.py + footprint.py + answers.py first")
            continue
        ex = by_id.get(eid)
        if not ex:
            continue
        var = json.loads(var_p.read_text())
        fp = {p["idx"]: p for p in json.loads(fp_p.read_text())["predictions"]}
        answer = json.loads(ans_p.read_text())["answer"]
        convo_orig = common.convo_string(ex["messages"], answer)
        convo_var = common.convo_string(var["messages_var"], answer)

        out = common.GRADES / f"{eid}.jsonl"
        done = graded_idxs(out)
        with out.open("a") as f:
            for r in ex["rubrics"]:
                if r["idx"] in done:
                    continue
                v_orig, _ = common.judge_criterion(convo_orig, r)
                v_var, _ = common.judge_criterion(convo_var, r)
                pred = fp.get(r["idx"], {"bucket": "kept", "age_sensitive": False})
                f.write(json.dumps({
                    "idx": r["idx"], "points": r["points"], "axis": r["axis"],
                    "predicted_bucket": pred["bucket"], "age_sensitive": pred["age_sensitive"],
                    "verdict_orig": v_orig, "verdict_var": v_var, "changed": v_orig != v_var,
                }) + "\n")
                f.flush()
                graded += 1
        print(f"graded {eid} ({len(ex['rubrics'])} criteria, age {var['age_from']}->{var['age_to']})")

    print(f"done: graded {graded} new criterion-pairs -> {common.GRADES}/")


if __name__ == "__main__":
    main()
