#!/usr/bin/env python3
"""Step 4 — generate the fixed model answer used for the locality test.

The V1/V2 test holds ONE answer fixed and re-grades it under the original and the
age-edited conversation, so that any verdict change is caused by the edit, not by a
different answer. We generate that answer to the ORIGINAL conversation V (target model,
thinking on — same as the baseline harness's generate.py).

Optionally (--also-variant) we also generate a *fresh* answer to V', for the adaptation
test (does the model change its answer appropriately when only the age changes?). That is
the optional E1 step 5; the kill-shot V1/V2 only needs the original answer.

Output: results/answers/<example_id>.json
    {example_id, model, think, answer, answer_var (optional)}
Resumable: skips items already answered (re-runs only to add a missing answer_var).

Usage:
    python3 src/answers.py                  # answer to V for every shortlisted item
    python3 src/answers.py --also-variant   # also answer to V' (adaptation test)
"""
import argparse
import json

import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    ap.add_argument("--also-variant", action="store_true",
                    help="also generate an answer to the edited conversation V' (adaptation test)")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.ANSWERS.mkdir(parents=True, exist_ok=True)
    ep = common.config.target_endpoint()
    common.endpoints_banner("(answers)", len(shortlist))

    done = skipped = 0
    for s in shortlist:
        out = common.ANSWERS / f"{s['example_id']}.json"
        rec = json.loads(out.read_text()) if out.exists() else None
        need_orig = rec is None
        need_var = args.also_variant and (rec is None or "answer_var" not in rec)
        if not need_orig and not need_var:
            skipped += 1
            continue
        ex = by_id.get(s["example_id"])
        if not ex:
            print(f"skip {s['example_id']}: not found in split")
            continue
        rec = rec or {"example_id": s["example_id"], "model": ep.model, "think": common.config.THINK_TARGET}
        if need_orig:
            rec["answer"] = common.target_answer(ex["messages"])
        if need_var:
            var = common.VARIANTS / f"{s['example_id']}.json"
            if not var.exists():
                print(f"skip variant for {s['example_id']}: run src/edit.py first")
            else:
                rec["answer_var"] = common.target_answer(json.loads(var.read_text())["messages_var"])
        common.atomic_write_json(out, rec)
        done += 1
        tag = "orig" + ("+var" if need_var else "")
        print(f"[{done}] {s['example_id']}  generated {tag}  ({len(rec.get('answer',''))} chars)")

    print(f"done: generated {done}, skipped {skipped} -> {common.ANSWERS}/")


if __name__ == "__main__":
    main()
