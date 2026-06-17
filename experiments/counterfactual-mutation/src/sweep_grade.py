#!/usr/bin/env python3
"""Step 5 — grade the model's FRESH answer to each input against the original rubric.

The answer model produced a response to every input (src/answers.py): A to the original
conversation V, and A_k to each swept variant V_k (src/sweep.py). Here we grade each
(input, its-own-answer) pair, per criterion, against the SAME original rubric, with the
temperature-0 judge — which only does the simple "does this answer satisfy this item?" check.

A criterion "changed" when the verdict of A_k under V_k differs from the verdict of A under V.
That flip means the model's answer to the mutated input satisfies the criterion differently —
which both identifies an input-dependent (footprint) criterion and shows whether the model
adapts. The rubric (curated for the input) holds the ground truth, so we change the input, let
the model answer, and let the flips fall out of the simple per-item judge check.

The many independent grader calls — (criterion x {V + each V_k}) per item — are fanned across
the judge endpoints with common.pmap so both GPUs stay busy. Judge explanations are stored.

Output: results/sweep_grades/<example_id>.jsonl, one line per criterion:
    {idx, points, axis, predicted_bucket, predicted_sensitive,
     verdict_orig, explanation_orig,
     sweep: [{value, label, verdict, explanation}, ...],   # K entries, in `values` order
     verdict_vector: [verdict_orig, v1, ..., vK], changed, flip_values, n_distinct_verdicts}
Resumable: skips (item, idx) pairs already graded.

Usage:
    python3 src/sweep_grade.py            # all items that have sweep + footprint + answers
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
        ans = json.loads(ans_p.read_text())
        answer_orig = ans.get("answer")
        var_answer = {va["value"]: va["answer"] for va in ans.get("variant_answers", [])}

        # Only grade variants whose own fresh answer exists; keep them in sweep `values` order.
        variants = [vr for vr in sweep["variants"] if var_answer.get(vr["value"])]
        if answer_orig is None or not variants:
            print(f"skip {eid}: missing fresh answers (run answers.py) — orig={answer_orig is not None}, "
                  f"variants={len(variants)}/{len(sweep['variants'])}")
            continue
        values = [vr["value"] for vr in variants]

        # Each input is graded with ITS OWN answer: V+A for the baseline, V_k+A_k per variant.
        convo_orig = common.convo_string(sweep["messages_orig"], answer_orig)
        convo_by_value = {vr["value"]: common.convo_string(vr["messages_var"], var_answer[vr["value"]])
                          for vr in variants}

        out = common.SWEEP_GRADES / f"{eid}.jsonl"
        done = graded_idxs(out)
        todo = [r for r in ex["rubrics"] if r["idx"] not in done]
        if not todo:
            continue

        work = []
        for r in todo:
            work.append((r["idx"], "orig", convo_orig, r))
            for v in values:
                work.append((r["idx"], v, convo_by_value[v], r))
        results = common.pmap(lambda item, ep: common.judge_criterion(item[2], item[3], endpoint=ep), work)

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
                pred = fp.get(idx, {"bucket": "kept", "predicted_sensitive": False})
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
        print(f"graded {eid} ({len(todo)} new criteria x {len(values)} variant answers, "
              f"{sweep['base_value']} -> {values})")

    print(f"done: graded {graded} criteria, {errored} deferred on error -> {common.SWEEP_GRADES}/")


if __name__ == "__main__":
    main()
