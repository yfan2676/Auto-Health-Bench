#!/usr/bin/env python3
"""Step 1' (D3+) — build shortlist rows FROM the applicable subagent overrides.

This inverts pick.py's order. For D1/D2, pick.py detects fit items in the split, then (for D2)
subagents author edits. For D3+ the subagent's "applicable" decision IS the detection, so we
materialize the shortlist straight from results/edits_override/<dimension>/*.json. The resulting
rows have exactly the fields sweep.py / build_viewer.py expect (dimension, base_value, label,
n_rubrics, axes) — sweep.py reads base via s.get("base_value", ...) and values()/edit_one() pull
the edit from the override file, so nothing downstream changes.

Composition matches pick.py: re-running a dimension replaces only that dimension's rows and keeps
every other dimension's rows (so D1, D2, and the other new dimensions are preserved).

Usage:
    python3 src/materialize_shortlist.py --dimension severity
    python3 src/materialize_shortlist.py                 # all D3+ dimensions at once
"""
import argparse
import json
from collections import Counter

import common

DIMS = ("severity", "pregnancy", "comorbidity", "sex")


def rows_for(dimension, by_id):
    d = common.EDITS_OVERRIDE / dimension
    files = sorted(d.glob("*.json")) if d.exists() else []
    rows, skipped = [], 0
    for f in files:
        try:
            ov = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        if not ov.get("applicable"):
            continue
        ex = by_id.get(ov.get("example_id", f.stem))
        if ex is None:
            skipped += 1
            continue
        axes = Counter(r["axis"] for r in ex["rubrics"] if r["axis"])
        rows.append({
            "example_id": ex["example_id"], "dimension": dimension,
            "base_value": ov.get("base_value"), "target_value": ov.get("target_value"),
            "label": ov.get("label", dimension),
            "n_rubrics": len(ex["rubrics"]), "axes": dict(axes),
        })
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", choices=DIMS, help="default: all D3+ dimensions")
    args = ap.parse_args()
    dims = [args.dimension] if args.dimension else list(DIMS)

    want = set()
    for dim in dims:
        d = common.EDITS_OVERRIDE / dim
        if d.exists():
            for f in d.glob("*.json"):
                try:
                    want.add(json.loads(f.read_text()).get("example_id", f.stem))
                except (json.JSONDecodeError, OSError):
                    want.add(f.stem)
    by_id = common.examples_by_id(want) if want else {}

    selected, per_dim = [], {}
    for dim in dims:
        rows, skipped = rows_for(dim, by_id)
        selected.extend(rows)
        per_dim[dim] = (len(rows), skipped)

    # Compose with existing shortlist: drop rows for the dimensions we're (re)building, keep others.
    rebuilding = set(dims)
    existing = []
    if common.SHORTLIST.exists():
        for line in common.SHORTLIST.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("dimension", "age") not in rebuilding:
                existing.append(row)
    common.RESULTS.mkdir(parents=True, exist_ok=True)
    with common.SHORTLIST.open("w") as fh:
        for row in existing + selected:
            fh.write(json.dumps(row) + "\n")

    kept = len(existing)
    print(f"materialized {len(selected)} rows for {dims} (kept {kept} from other dimensions) "
          f"-> {common.SHORTLIST}")
    for dim, (n, skipped) in per_dim.items():
        print(f"  {dim}: {n} applicable rows" + (f"  ({skipped} skipped)" if skipped else ""))


if __name__ == "__main__":
    main()
