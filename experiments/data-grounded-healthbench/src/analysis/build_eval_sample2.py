#!/usr/bin/env python3
"""Extend the LLM-judge sample from 200 -> 600 conversations.

Preserves the original 200 (seed 20260604) as idx 0..199 so the existing
judge_0..4.json stay valid, then draws 400 MORE disjoint conversations
(seed 20260605) as idx 200..599 in batch_5..14.jsonl, and rewrites
sample_meta.jsonl to cover all 600.
"""
import json
import random
from pathlib import Path

import importlib.util
spec = importlib.util.spec_from_file_location("u", "src/analysis/user_data_scan.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

OUT = Path("data/derived/udeval")
PER = 40


def main():
    rows = [json.loads(l) for l in Path("data/derived/index.jsonl").open()]

    # reproduce the original 200 exactly (idx 0..199)
    random.seed(20260604)
    first = random.sample(rows, 200)
    chosen = {r["example_id"] for r in first}

    # draw 400 more, disjoint
    remaining = [r for r in rows if r["example_id"] not in chosen]
    random.seed(20260605)
    extra = random.sample(remaining, 400)

    full = first + extra  # idx 0..599
    OUT.mkdir(parents=True, exist_ok=True)

    # rewrite combined meta (idx mapping for 0..199 unchanged)
    with (OUT / "sample_meta.jsonl").open("w") as mf:
        for idx, r in enumerate(full):
            txt = u.user_text(r)
            hits = u.detect(txt)
            mf.write(json.dumps({
                "idx": idx, "example_id": r["example_id"],
                "heuristic_strict": bool(hits),
                "heuristic_categories": sorted(hits.keys()),
                "heuristic_dx": bool(u.RE_DX.search(txt)),
            }) + "\n")

    # write ONLY the new batches (5..14) for idx 200..599
    n_first = len(first)  # 200
    for b in range(10):
        lo = n_first + b * PER
        chunk = full[lo:lo + PER]
        with (OUT / f"batch_{5 + b}.jsonl").open("w") as bf:
            for i, r in enumerate(chunk):
                idx = lo + i
                bf.write(json.dumps({"idx": idx, "example_id": r["example_id"],
                                     "user_text": u.user_text(r)}) + "\n")
    print(f"total sample = {len(full)}; wrote new batches 5..14 (idx 200..599); "
          f"meta rewritten for all {len(full)}")


if __name__ == "__main__":
    main()
