#!/usr/bin/env python3
"""Step 2 — generate fresh answers: 3 to the ORIGINAL input and 3 to the chosen MUTATION.

Driven by results/selection.jsonl (src/sample.py): one mutated variant per sample. For each
sample we generate CR_RUNS (default 3) independent answers to the original conversation V and
CR_RUNS independent answers to the chosen mutated conversation V'. The runs are independent
samples at the target temperature (thinking on); replicating lets us separate the mutation's
effect on the score from the model's own run-to-run noise (the 3 original runs ARE that noise
baseline). The grades come later (src/grade.py); here we only produce the responses.

Generation is the slow step, so ALL answers (across samples, conditions, and runs) are produced
in one concurrent batch, round-robined across the answer-model endpoints (HB_TARGET_BASE_URLS)
so every GPU stays busy. This is the "generate everything first, then grade everything" split.

Output: results/answers_<version>/<example_id>.json
    {example_id, model, think, chosen_value, chosen_label,
     orig_answers: [a0, a1, a2], mut_answers: [a0, a1, a2]}
Resumable: pre-sizes the two lists to CR_RUNS and fills only the empty (condition, run) cells.

Usage:
    python3 src/answers.py
    python3 src/answers.py --limit 4      # first N selected samples
"""
import argparse
import json

import common

RUNS = common.CR_RUNS


def _variant_messages(sweep, chosen_value):
    """The messages of the chosen mutated variant (matched by value) from a sweep file."""
    for vr in sweep.get("variants", []):
        if vr["value"] == chosen_value:
            return vr["messages_var"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N selected samples (0 = all)")
    args = ap.parse_args()

    selection = common.load_selection()
    if args.limit:
        selection = selection[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in selection])
    common.ANSWERS.mkdir(parents=True, exist_ok=True)
    gen_model = common.GEN_EPS[0].model
    print(f"answer-model={gen_model}@{[e.base_url for e in common.GEN_EPS]}  "
          f"think={common.config.THINK_TARGET}  runs={RUNS}  samples={len(selection)}")

    # One flat work list of (eid, condition, run, messages) across all samples, skipping any
    # cell already answered, then generate them all concurrently across the answer-model GPUs.
    recs = {}          # eid -> the answers record we are assembling
    work = []          # list of (eid, condition, run)
    work_msgs = []     # aligned messages to answer
    for s in selection:
        eid = s["example_id"]
        ex = by_id.get(eid)
        sweep_p = common.SWEEP / f"{eid}.json"
        if not ex or not sweep_p.exists():
            print(f"  ! {eid}: missing example or sweep file, skipping")
            continue
        sweep = json.loads(sweep_p.read_text())
        mut_msgs = _variant_messages(sweep, s["chosen_value"])
        if mut_msgs is None:
            print(f"  ! {eid}: chosen variant {s['chosen_value']!r} not in sweep, skipping")
            continue
        orig_msgs = sweep.get("messages_orig", ex["messages"])

        ans_p = common.ANSWERS / f"{eid}.json"
        rec = json.loads(ans_p.read_text()) if ans_p.exists() else {
            "example_id": eid, "model": gen_model, "think": common.config.THINK_TARGET,
            "chosen_value": s["chosen_value"], "chosen_label": s["chosen_label"],
            "orig_answers": [], "mut_answers": []}
        # Pre-size the run lists to RUNS (pad with None) so we can fill missing cells in place.
        for key in ("orig_answers", "mut_answers"):
            lst = rec.get(key) or []
            lst += [None] * (RUNS - len(lst))
            rec[key] = lst[:RUNS]
        recs[eid] = rec

        for run in range(RUNS):
            if not rec["orig_answers"][run]:
                work.append((eid, "orig", run)); work_msgs.append(orig_msgs)
            if not rec["mut_answers"][run]:
                work.append((eid, "mut", run)); work_msgs.append(mut_msgs)

    if not work:
        print("nothing to do: all answers already generated")
        return

    print(f"generating {len(work)} answers concurrently across {len(common.GEN_EPS)} endpoint(s)...")
    results = common.pmap(lambda msgs, ep: common.target_answer(msgs, endpoint=ep),
                          work_msgs, endpoints=common.GEN_EPS)

    errors = 0
    for (eid, cond, run), res in zip(work, results):
        if isinstance(res, Exception) or res is None:
            errors += 1
            print(f"  ! {eid} [{cond} run{run}]: generation error "
                  f"({type(res).__name__ if res else 'none'}: {res}), will retry on resume")
            continue
        recs[eid]["orig_answers" if cond == "orig" else "mut_answers"][run] = res
    for eid, rec in recs.items():
        common.atomic_write_json(common.ANSWERS / f"{eid}.json", rec)

    done = len(work) - errors
    print(f"done: generated {done} answers ({errors} deferred on error) -> {common.ANSWERS}/")


if __name__ == "__main__":
    main()
