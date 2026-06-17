#!/usr/bin/env python3
"""Step 5' — the sweep locality test (generalizes paired_grade.py to K values).

For each item we take the FIXED answer to the original conversation and grade it, per
criterion, under the original conversation V and under each of the K swept variants V_k
(src/sweep.py), with the temperature-0 judge. Because the answer is identical everywhere,
any verdict change is caused by the dimension edit, not by a different answer. A criterion
is in the MEASURED FOOTPRINT iff its verdict differs from the original at ANY swept value;
otherwise it is in the bridge (invariant across the whole sweep). `flip_values` records
*where* it flips (e.g. a screening cutoff near a certain age) — a clinically readable bonus.

This is the behavioral footprint of the idea doc §4.1 — the stronger ground truth that the
a-priori footprint classifier (src/footprint.py) is then scored against in src/analyze.py.

The many independent grader calls — (criterion x {orig + K values}) for every item — are
fanned across the judge endpoints with common.pmap so both GPUs stay busy (vs the ~1 req/s
serial baseline). Judge explanations are stored (the viewer shows them side by side).

Output: results/sweep_grades/<example_id>.jsonl, one line per criterion:
    {idx, points, axis, predicted_bucket, predicted_sensitive,
     verdict_orig, explanation_orig,
     sweep: [{value, label, verdict, explanation}, ...],   # K entries, in `values` order
     verdict_vector: [verdict_orig, v1, ..., vK], changed, flip_values, n_distinct_verdicts}
Resumable: skips (item, idx) pairs already graded.

Usage:
    python3 src/sweep_grade.py            # all items that have sweep + footprint + answer
    python3 src/sweep_grade.py --limit 2
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
    common.SWEEP_GRADES.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(sweep_grade)", len(shortlist))

    graded = errored = 0
    for s in shortlist:
        eid = s["example_id"]
        sweep_p = common.SWEEP / f"{eid}.json"
        fp_p = common.FOOTPRINT / f"{eid}.json"
        ans_p = common.ANSWERS / f"{eid}.json"
        if not (sweep_p.exists() and fp_p.exists() and ans_p.exists()):
            print(f"skip {eid}: needs sweep.py + footprint.py + answers.py first")
            continue
        ex = by_id.get(eid)
        if not ex:
            continue

        sweep = json.loads(sweep_p.read_text())
        fp = {p["idx"]: p for p in json.loads(fp_p.read_text())["predictions"]}
        answer = json.loads(ans_p.read_text())["answer"]
        variants = sweep["variants"]
        values = [vr["value"] for vr in variants]

        convo_orig = common.convo_string(sweep["messages_orig"], answer)
        convo_by_value = {vr["value"]: common.convo_string(vr["messages_var"], answer) for vr in variants}

        out = common.SWEEP_GRADES / f"{eid}.jsonl"
        done = graded_idxs(out)
        todo = [r for r in ex["rubrics"] if r["idx"] not in done]
        if not todo:
            continue

        # One flat work list across this item's remaining criteria x {orig + K values};
        # pmap round-robins it across the judge GPUs. slot = "orig" or a swept value.
        work = []
        for r in todo:
            work.append((r["idx"], "orig", convo_orig, r))
            for v in values:
                work.append((r["idx"], v, convo_by_value[v], r))
        results = common.pmap(lambda item, ep: common.judge_criterion(item[2], item[3], endpoint=ep), work)

        # Regroup by criterion idx: {idx: {"orig": (met, expl), value: (met, expl), ...}}.
        graded_by_idx = {}
        for (idx, slot, _convo, _r), res in zip(work, results):
            graded_by_idx.setdefault(idx, {})[slot] = res

        with out.open("a") as f:
            for r in todo:
                idx = r["idx"]
                slots = graded_by_idx.get(idx, {})
                cells = [slots.get("orig")] + [slots.get(v) for v in values]
                if any(c is None or isinstance(c, Exception) for c in cells):
                    bad = next((c for c in cells if isinstance(c, Exception)), None)
                    print(f"  ! {eid} idx {idx}: grading error, will retry on resume "
                          f"({type(bad).__name__ + ': ' + str(bad) if bad else 'missing cell'})")
                    errored += 1
                    continue
                (v_orig, e_orig) = cells[0]
                sweep_cells = [
                    {"value": vr["value"], "label": vr["label"],
                     "verdict": cells[i + 1][0], "explanation": cells[i + 1][1]}
                    for i, vr in enumerate(variants)
                ]
                verdict_vector = [v_orig] + [c["verdict"] for c in sweep_cells]
                flip_values = [c["value"] for c in sweep_cells if c["verdict"] != v_orig]
                pred = fp.get(idx, {"bucket": "kept", "age_sensitive": False})
                bucket = pred.get("bucket", "kept")
                predicted_sensitive = pred.get(
                    "predicted_sensitive", pred.get("age_sensitive", bucket != "kept"))
                f.write(json.dumps({
                    "idx": idx, "points": r["points"], "axis": r["axis"],
                    "predicted_bucket": bucket, "predicted_sensitive": bool(predicted_sensitive),
                    "verdict_orig": v_orig, "explanation_orig": e_orig,
                    "sweep": sweep_cells,
                    "verdict_vector": verdict_vector,
                    "changed": bool(flip_values),
                    "flip_values": flip_values,
                    "n_distinct_verdicts": len(set(verdict_vector)),
                }) + "\n")
                f.flush()
                graded += 1
        print(f"graded {eid} ({len(todo)} new criteria x {len(values)} values, "
              f"{sweep['base_value']} -> {values})")

    print(f"done: graded {graded} criteria, {errored} deferred on error -> {common.SWEEP_GRADES}/")


if __name__ == "__main__":
    main()
