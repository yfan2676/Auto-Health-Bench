#!/usr/bin/env python3
"""Phase 2 (all-30) — build the work-batch manifest for the subagent fan-out.

Splits the entries that still need scoring into batches and writes a manifest
the mutation / response / grading subagents read by batch index.
"""
import json
from pathlib import Path

OUT = Path("results/phase2")
DONE = {"ad5cf7e5", "553b75c2"}  # the 2 already fully run in the PoC


def chunk(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def main():
    cases = json.loads((OUT / "cases_all.json").read_text())
    all_id8 = [c["id8"] for c in cases]
    todo = [x for x in all_id8 if x not in DONE]
    manifest = {
        "all": all_id8,
        "done": [x for x in all_id8 if x in DONE],
        "todo": todo,
        "mutation": chunk(todo, 7),   # 4 batches
        "work": chunk(todo, 4),       # 7 batches (responses + grading)
    }
    (OUT / "batches.json").write_text(json.dumps(manifest, indent=2))
    print(f"total={len(all_id8)} done={len(manifest['done'])} todo={len(todo)}")
    print(f"mutation batches={len(manifest['mutation'])} (size 7)")
    print(f"work batches={len(manifest['work'])} (size 4)")


if __name__ == "__main__":
    main()
