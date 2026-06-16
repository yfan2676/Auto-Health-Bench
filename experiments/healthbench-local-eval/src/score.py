#!/usr/bin/env python3
"""Aggregate grades.jsonl into HealthBench scores.

Mirrors openai/simple-evals scoring:
  per example   score = achieved_points / total_possible_points
                where total_possible_points = sum(points where points > 0)
                and   achieved_points       = sum(points where criteria_met)
  overall       = clip(mean(per-example scores), 0, 1)

Per-example tags (themes, physician categories) take the example's overall score;
rubric-level tags (axis:*) are scored over just the items carrying that tag. Each
aggregate is the clipped mean across examples (matching the reference).

Only examples whose every rubric item has been graded are scored, so partial
progress from an interrupted grading run is excluded rather than mis-scored.

Usage (from the experiment directory):
    python3 src/score.py --split full --limit 25
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import config
import data

GRADES = Path("results/grades.jsonl")
OUT = Path("results/score.json")


def calc_score(items):
    """items: list of {points, criteria_met}. Returns achieved/possible, or None
    if there are no positive-point items (score undefined)."""
    total_possible = sum(it["points"] for it in items if it["points"] > 0)
    if total_possible == 0:
        return None
    achieved = sum(it["points"] for it in items if it["criteria_met"])
    return achieved / total_possible


def clipped_mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return max(0.0, min(1.0, sum(values) / len(values)))


def load_grades():
    grades = defaultdict(dict)  # example_id -> {idx: criteria_met}
    if not GRADES.exists():
        raise FileNotFoundError(f"{GRADES} not found — run grade.py first")
    for line in GRADES.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        grades[rec["example_id"]][rec["idx"]] = rec["criteria_met"]
    return grades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=25, help="first N examples (0 = all)")
    args = ap.parse_args()

    examples = data.load_split(args.split, args.limit or None)
    grades = load_grades()

    per_example = []           # raw per-example overall scores
    theme_scores = defaultdict(list)
    axis_scores = defaultdict(list)
    n_complete = 0

    for ex in examples:
        eid = ex["example_id"]
        graded = grades.get(eid, {})
        # require every rubric item graded
        if not ex["rubrics"] or any(r["idx"] not in graded for r in ex["rubrics"]):
            continue
        n_complete += 1
        items = [
            {"points": r["points"], "criteria_met": graded[r["idx"]],
             "axis": r["axis"]}
            for r in ex["rubrics"]
        ]
        overall = calc_score(items)
        if overall is None:
            continue
        per_example.append(overall)
        for tag in ex["example_tags"]:
            theme_scores[tag].append(overall)
        by_axis = defaultdict(list)
        for it in items:
            if it["axis"]:
                by_axis[it["axis"]].append(it)
        for axis, its in by_axis.items():
            s = calc_score(its)
            if s is not None:
                axis_scores[axis].append(s)

    result = {
        "split": args.split,
        "model": config.target_endpoint().model,
        "judge": config.judge_endpoint().model,
        "n_examples": len(examples),
        "n_scored": len(per_example),
        "n_complete": n_complete,
        "overall_score": clipped_mean(per_example),
        "per_axis": {k: clipped_mean(v) for k, v in sorted(axis_scores.items())},
        "per_theme": {
            k.split(":", 1)[1]: clipped_mean(v)
            for k, v in sorted(theme_scores.items())
            if k.startswith("theme:")
        },
    }
    OUT.write_text(json.dumps(result, indent=2))

    overall = result["overall_score"]
    print(f"split={args.split}  scored {result['n_scored']}/{result['n_examples']} examples")
    print(f"overall HealthBench score: {overall:.4f}" if overall is not None else "overall: n/a")
    if result["per_axis"]:
        print("by axis:")
        for k, v in result["per_axis"].items():
            print(f"  {k:<22} {v:.4f}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
