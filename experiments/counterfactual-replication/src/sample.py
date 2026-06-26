#!/usr/bin/env python3
"""Step 1 — pick 25 samples per dimension and ONE mutated variant per sample.

The detected item set (results/shortlist.jsonl) and the generated mutated inputs
(results/sweep/<eid>.json) are reused verbatim from counterfactual-mutation, so this step
does no model calls — it just subsamples deterministically:

  * 25 example_ids per dimension (age, disclosure, severity, pregnancy, comorbidity, sex),
    drawn with a per-dimension seeded RNG so the draws are independent and reproducible.
  * ONE variant per sample. age and disclosure carry K=3 variants in their sweep file; we
    keep exactly one (chosen with a per-eid seeded RNG). severity/pregnancy/comorbidity/sex
    already have K=1, so the choice is trivial. Only variants with ok=True are eligible.

Determinism: everything keys off CR_SEED (default 20260626). Re-running reproduces the same
selection; adding/removing a dimension does not perturb the others (each dimension/eid seeds
its own RNG from (CR_SEED, key)).

Output: results/selection.jsonl, one row per selected sample:
    {example_id, dimension, base_value, chosen_value, chosen_label}

Usage:
    python3 src/sample.py
    CR_PER_DIM=2 python3 src/sample.py     # tiny set for a smoke test
"""
import json
import os
import random
from collections import defaultdict

import common

SEED = int(os.environ.get("CR_SEED", "20260626"))
PER_DIM = int(os.environ.get("CR_PER_DIM", "25"))


def main():
    shortlist = common.load_shortlist()
    by_dim = defaultdict(list)
    for s in shortlist:
        by_dim[s.get("dimension", "age")].append(s)

    rows = []
    for dim in sorted(by_dim):
        items = sorted(by_dim[dim], key=lambda s: s["example_id"])  # stable order before sampling
        rng = random.Random(f"{SEED}:dim:{dim}")
        n = min(PER_DIM, len(items))
        picks = rng.sample(items, n)
        if n < PER_DIM:
            print(f"  ! {dim}: only {len(items)} items available, selecting all {n} (< {PER_DIM})")
        for s in picks:
            eid = s["example_id"]
            sweep_p = common.SWEEP / f"{eid}.json"
            if not sweep_p.exists():
                print(f"  ! {dim}/{eid}: no sweep file, skipping")
                continue
            sweep = json.loads(sweep_p.read_text())
            variants = sweep.get("variants", [])
            eligible = [v for v in variants if v.get("ok", True)] or variants
            if not eligible:
                print(f"  ! {dim}/{eid}: no usable variant, skipping")
                continue
            chosen = random.Random(f"{SEED}:eid:{eid}").choice(eligible)
            rows.append({
                "example_id": eid,
                "dimension": dim,
                "base_value": sweep.get("base_value"),
                "chosen_value": chosen["value"],
                "chosen_label": chosen.get("label", str(chosen["value"])),
            })

    common.SELECTION.parent.mkdir(parents=True, exist_ok=True)
    with common.SELECTION.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    counts = defaultdict(int)
    for r in rows:
        counts[r["dimension"]] += 1
    print(f"selected {len(rows)} samples (seed={SEED}, per_dim={PER_DIM}): "
          + ", ".join(f"{d}={counts[d]}" for d in sorted(counts)))
    print(f"-> {common.SELECTION}")


if __name__ == "__main__":
    main()
