#!/usr/bin/env python3
"""Step 3 — grade every answer (orig x3 + mut x3) against the ORIGINAL rubric.

src/answers.py produced CR_RUNS fresh answers to the original input V and CR_RUNS to the chosen
mutated input V'. Here each (input, its-own-answer) pair is graded per criterion against the
SAME original rubric, with the thinking judge. Grading the mutated answer against the original
rubric is the controlled comparison: identical yardstick, only the input changed, so any change
in the overall rubric score is attributable to the mutation (tested for significance in
src/analyze.py).

All independent grader calls — (criterion x {orig run, mut run}) per sample — are fanned across
the judge endpoints with common.pmap so every GPU stays busy. This runs AFTER all generation.

Output: results/grades_<version>/<example_id>.jsonl, one line per criterion:
    {idx, points, axis,
     orig: [{run, verdict, explanation}, ...],   # CR_RUNS entries
     mut:  [{run, verdict, explanation}, ...]}    # CR_RUNS entries
Resumable: skips criteria already fully graded (all 2*CR_RUNS cells present).

Usage:
    python3 src/grade.py
    python3 src/grade.py --limit 2
"""
import argparse
import json

import common

RUNS = common.CR_RUNS


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


def _variant(sweep, value):
    for vr in sweep.get("variants", []):
        if vr["value"] == value:
            return vr
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N selected samples (0 = all)")
    args = ap.parse_args()

    selection = common.load_selection()
    if args.limit:
        selection = selection[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in selection])
    common.GRADES.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(grade)", len(selection))

    graded = errored = 0
    for s in selection:
        eid = s["example_id"]
        sweep_p = common.SWEEP / f"{eid}.json"
        ans_p = common.ANSWERS / f"{eid}.json"
        if not (sweep_p.exists() and ans_p.exists()):
            print(f"skip {eid}: needs sample.py + answers.py first")
            continue
        ex = by_id.get(eid)
        if not ex:
            continue

        sweep = json.loads(sweep_p.read_text())
        ans = json.loads(ans_p.read_text())
        orig_answers = ans.get("orig_answers", [])
        mut_answers = ans.get("mut_answers", [])
        variant = _variant(sweep, s["chosen_value"])
        if variant is None:
            print(f"skip {eid}: chosen variant {s['chosen_value']!r} not in sweep")
            continue
        # Need all CR_RUNS answers on both sides before grading this sample.
        if not (all(orig_answers[:RUNS]) and all(mut_answers[:RUNS]) and
                len(orig_answers) >= RUNS and len(mut_answers) >= RUNS):
            print(f"skip {eid}: missing fresh answers (run answers.py) — "
                  f"orig={sum(1 for a in orig_answers[:RUNS] if a)}/{RUNS}, "
                  f"mut={sum(1 for a in mut_answers[:RUNS] if a)}/{RUNS}")
            continue

        # Each input/run is graded with ITS OWN answer: V+A_r for orig, V'+A'_r for mut.
        convo_orig = [common.convo_string(sweep["messages_orig"], orig_answers[r]) for r in range(RUNS)]
        convo_mut = [common.convo_string(variant["messages_var"], mut_answers[r]) for r in range(RUNS)]

        out = common.GRADES / f"{eid}.jsonl"
        done = graded_idxs(out)
        todo = [r for r in ex["rubrics"] if r["idx"] not in done]
        if not todo:
            continue

        # Build the 2*RUNS judge cells per criterion: (idx, condition, run, convo, rubric).
        work = []
        for r in todo:
            for run in range(RUNS):
                work.append((r["idx"], "orig", run, convo_orig[run], r))
                work.append((r["idx"], "mut", run, convo_mut[run], r))
        results = common.pmap(lambda item, ep: common.judge_criterion(item[3], item[4], endpoint=ep), work)

        # Collect cells per criterion: graded_by_idx[idx][(condition, run)] = (verdict, explanation)|Exception
        graded_by_idx = {}
        for (idx, cond, run, _convo, _r), res in zip(work, results):
            graded_by_idx.setdefault(idx, {})[(cond, run)] = res

        with out.open("a") as f:
            for r in todo:
                idx = r["idx"]
                slots = graded_by_idx.get(idx, {})
                cells = [slots.get((c, run)) for c in ("orig", "mut") for run in range(RUNS)]
                if any(c is None or isinstance(c, Exception) for c in cells):
                    bad = next((c for c in cells if isinstance(c, Exception)), None)
                    print(f"  ! {eid} idx {idx}: grading error, will retry on resume "
                          f"({type(bad).__name__ + ': ' + str(bad) if bad else 'missing cell'})")
                    errored += 1
                    continue
                row = {"idx": idx, "points": r["points"], "axis": r["axis"], "orig": [], "mut": []}
                for cond in ("orig", "mut"):
                    for run in range(RUNS):
                        verdict, expl = slots[(cond, run)]
                        row[cond].append({"run": run, "verdict": verdict, "explanation": expl})
                f.write(json.dumps(row) + "\n")
                f.flush()
                graded += 1
        print(f"graded {eid} ({len(todo)} new criteria x {2 * RUNS} cells, "
              f"{sweep.get('base_value')} -> {s['chosen_label']})")

    print(f"done: graded {graded} criteria, {errored} deferred on error -> {common.GRADES}/")


if __name__ == "__main__":
    main()
