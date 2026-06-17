#!/usr/bin/env python3
"""Step 4 — generate a FRESH answer from the answer model for EVERY input.

The experiment probes the answer model: we change the input and let the model respond, then
grade that fresh response against the original rubric (src/sweep_grade.py). So here we
generate one answer per input — the original conversation V *and* each swept variant V_k
(from src/sweep.py) — with the target model (thinking on, same as the baseline harness).
A criterion later "flips" when the model's answer to V_k satisfies it differently than its
answer to V; that flip is what identifies an input-dependent (footprint) criterion and shows
whether the model adapts. The rubric — curated for the input — holds the ground truth for how a
good answer should change, so we probe the answer model on each input and let the judge do only
the simple per-item check.

Generation is the slow step, so all answers (across items and inputs) are produced
concurrently, round-robined across the answer-model endpoints (HB_TARGET_BASE_URLS) so both
GPUs stay busy.

Output: results/answers/<example_id>.json
    {example_id, model, think, answer, variant_answers: [{value, answer}, ...]}
Resumable: skips items already fully answered (fills only missing inputs).

Usage:
    python3 src/answers.py            # answer V and every V_k for all shortlisted items
    python3 src/answers.py --limit 2
"""
import argparse
import json

import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.ANSWERS.mkdir(parents=True, exist_ok=True)
    gen_model = common.GEN_EPS[0].model
    print(f"answer-model={gen_model}@{[e.base_url for e in common.GEN_EPS]}  "
          f"think={common.config.THINK_TARGET}  items={len(shortlist)}")

    # Build one flat work list of (eid, slot, messages) across all items, skipping any input
    # already answered, then generate them all concurrently across the answer-model GPUs.
    recs = {}          # eid -> the answers record we are assembling
    work = []          # list of (eid, slot)  where slot is "orig" or a variant value
    work_msgs = []     # aligned messages to answer
    for s in shortlist:
        eid = s["example_id"]
        ex = by_id.get(eid)
        if not ex:
            continue
        sweep_p = common.SWEEP / f"{eid}.json"
        sweep = json.loads(sweep_p.read_text()) if sweep_p.exists() else None
        ans_p = common.ANSWERS / f"{eid}.json"
        rec = json.loads(ans_p.read_text()) if ans_p.exists() else {
            "example_id": eid, "model": gen_model, "think": common.config.THINK_TARGET,
            "answer": None, "variant_answers": []}
        rec.setdefault("variant_answers", [])
        recs[eid] = rec

        if not rec.get("answer"):
            work.append((eid, "orig")); work_msgs.append(ex["messages"])
        have = {va["value"] for va in rec["variant_answers"]}
        for vr in (sweep["variants"] if sweep else []):
            if vr["value"] not in have:
                work.append((eid, vr["value"])); work_msgs.append(vr["messages_var"])

    if not work:
        print("nothing to do: all inputs already answered")
        return

    print(f"generating {len(work)} answers concurrently across {len(common.GEN_EPS)} endpoint(s)...")
    results = common.pmap(lambda msgs, ep: common.target_answer(msgs, endpoint=ep),
                          work_msgs, endpoints=common.GEN_EPS)

    # Fold results back into each item's record and write.
    errors = 0
    for (eid, slot), res in zip(work, results):
        if isinstance(res, Exception) or res is None:
            errors += 1
            print(f"  ! {eid} [{slot}]: generation error ({type(res).__name__ if res else 'none'}), will retry on resume")
            continue
        rec = recs[eid]
        if slot == "orig":
            rec["answer"] = res
        else:
            rec["variant_answers"] = [va for va in rec["variant_answers"] if va["value"] != slot]
            rec["variant_answers"].append({"value": slot, "answer": res})
    for eid, rec in recs.items():
        common.atomic_write_json(common.ANSWERS / f"{eid}.json", rec)

    done = sum(1 for (_, _), r in zip(work, results) if not (isinstance(r, Exception) or r is None))
    print(f"done: generated {done} answers ({errors} deferred on error) -> {common.ANSWERS}/")


if __name__ == "__main__":
    main()
