#!/usr/bin/env python3
"""Step 6 — measure the judge-noise floor (so V1's off-target rate is interpretable).

The bridge-invariance result (V1) is only meaningful relative to how often the judge flips
its own verdict on the IDENTICAL input. We grade the same (original conversation, fixed
answer, criterion) triple K times and record the fraction of criteria whose K verdicts are
not unanimous. At the temperature-0 default this should be near zero; whatever it is, the
analysis compares the off-target change rate against it rather than against zero.

Output: results/noise_floor.json
    {k, judge_temp, judge_think, n_criteria, n_unstable, flip_rate, examples_used}

Usage:
    python3 src/noise_floor.py --k 5 --items 5 --max-criteria 8
"""
import argparse
import json

import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="repeat gradings per criterion")
    ap.add_argument("--items", type=int, default=5, help="number of shortlisted items to sample")
    ap.add_argument("--max-criteria", type=int, default=8, help="cap criteria per item")
    args = ap.parse_args()

    shortlist = common.load_shortlist()[:args.items]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.RESULTS.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(noise_floor)", len(shortlist))

    n_criteria = n_unstable = 0
    used = []
    for s in shortlist:
        eid = s["example_id"]
        ans_p = common.ANSWERS / f"{eid}.json"
        ex = by_id.get(eid)
        if not (ans_p.exists() and ex):
            continue
        answer = json.loads(ans_p.read_text())["answer"]
        convo = common.convo_string(ex["messages"], answer)
        used.append(eid)
        for r in ex["rubrics"][:args.max_criteria]:
            verdicts = [common.judge_criterion(convo, r)[0] for _ in range(args.k)]
            n_criteria += 1
            if len(set(verdicts)) > 1:
                n_unstable += 1
        print(f"{eid}: sampled {min(len(ex['rubrics']), args.max_criteria)} criteria x{args.k}")

    flip_rate = (n_unstable / n_criteria) if n_criteria else 0.0
    rec = {"k": args.k, "judge_temp": common.CM_JUDGE_TEMP, "judge_think": common.CM_JUDGE_THINK,
           "n_criteria": n_criteria, "n_unstable": n_unstable, "flip_rate": round(flip_rate, 4),
           "examples_used": used}
    common.atomic_write_json(common.RESULTS / "noise_floor.json", rec)
    print(f"noise floor: {n_unstable}/{n_criteria} criteria unstable across k={args.k} "
          f"({flip_rate:.1%}) -> results/noise_floor.json")


if __name__ == "__main__":
    main()
