#!/usr/bin/env python3
"""Step 1 — select HealthBench items FIT for a dimension (age, disclosure, ...).

Detection is delegated to the dimension (src/dimensions/): D1 (age) is a regex over the
patient text; D2 (disclosure) is a regex prefilter + an LLM confirm that a stated fact is
re-encodable as data. Selection only guarantees the dimension has something to edit; whether
an item actually has a sensitive rubric footprint is decided later (footprint.py / the sweep).

The shortlist is keyed by dimension, so D1 and D2 items COEXIST in one file: re-running pick
for a dimension replaces just that dimension's rows and preserves the others. Each row carries
`dimension` + whatever fields the dimension stashed in detect (e.g. age_from/age_str for age;
encoding_kind/fact/stated_span for disclosure).

Output: results/shortlist.jsonl, one object per selected item.

Usage:
    python3 src/pick.py --dimension age        --limit 30
    python3 src/pick.py --dimension disclosure  --limit 30   # appends; keeps the age rows
"""
import argparse
import json
from collections import Counter

import common
import dimensions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", default="age", choices=dimensions.names())
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=30, help="keep first N fit items (0 = all)")
    ap.add_argument("--scan", type=int, default=0, help="scan only the first N examples (0 = all)")
    args = ap.parse_args()

    dim = dimensions.get(args.dimension)
    examples = common.load_split(args.split, args.scan or None)
    common.RESULTS.mkdir(parents=True, exist_ok=True)

    selected = []
    for ex in examples:
        fields = dim.detect(ex)
        if not fields:
            continue
        axes = Counter(r["axis"] for r in ex["rubrics"] if r["axis"])
        selected.append({"example_id": ex["example_id"], **fields,
                         "n_rubrics": len(ex["rubrics"]), "axes": dict(axes)})
        if args.limit and len(selected) >= args.limit:
            break

    # Compose with any existing shortlist: drop this dimension's old rows, keep the rest.
    existing = []
    if common.SHORTLIST.exists():
        for line in common.SHORTLIST.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("dimension", "age") != args.dimension:
                existing.append(row)
    with common.SHORTLIST.open("w") as f:
        for row in existing + selected:
            f.write(json.dumps(row) + "\n")

    kept = len(existing)
    print(f"scanned {len(examples)} examples; selected {len(selected)} fit for '{args.dimension}'"
          f" (kept {kept} from other dimensions) -> {common.SHORTLIST}")
    if selected:
        s0 = selected[0]
        print(f"example: id={s0['example_id']} {s0.get('label', '')}"
              + (f" base={s0.get('base_value')}" if 'base_value' in s0 else ""))


if __name__ == "__main__":
    main()
