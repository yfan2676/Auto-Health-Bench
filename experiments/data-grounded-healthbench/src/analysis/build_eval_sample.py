#!/usr/bin/env python3
"""Draw a reproducible random sample of HealthBench conversations for LLM judging,
to calibrate the user_data_scan heuristic and produce an unbiased prevalence.

Writes (all gitignored, under data/derived/udeval/):
  batch_<k>.jsonl  — {idx, example_id, user_text} for each judge agent
  sample_meta.jsonl — {idx, example_id, heuristic_strict, heuristic_categories, heuristic_dx}
"""
import json
import random
from pathlib import Path

import importlib.util
spec = importlib.util.spec_from_file_location("u", "src/analysis/user_data_scan.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

N = 200
N_BATCHES = 5
OUT = Path("data/derived/udeval")


def main():
    rows = [json.loads(l) for l in Path("data/derived/index.jsonl").open()]
    random.seed(20260604)
    sample = random.sample(rows, N)
    OUT.mkdir(parents=True, exist_ok=True)

    meta = OUT / "sample_meta.jsonl"
    with meta.open("w") as mf:
        per = (N + N_BATCHES - 1) // N_BATCHES
        for b in range(N_BATCHES):
            chunk = sample[b * per:(b + 1) * per]
            with (OUT / f"batch_{b}.jsonl").open("w") as bf:
                for i, r in enumerate(chunk):
                    idx = b * per + i
                    txt = u.user_text(r)
                    bf.write(json.dumps({"idx": idx, "example_id": r["example_id"],
                                         "user_text": txt}) + "\n")
                    hits = u.detect(txt)
                    mf.write(json.dumps({
                        "idx": idx, "example_id": r["example_id"],
                        "heuristic_strict": bool(hits),
                        "heuristic_categories": sorted(hits.keys()),
                        "heuristic_dx": bool(u.RE_DX.search(txt)),
                    }) + "\n")
    print(f"wrote {N} examples across {N_BATCHES} batches to {OUT}/")


if __name__ == "__main__":
    main()
