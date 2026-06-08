#!/usr/bin/env python3
"""Phase 1 / Step 1 — Rubric mining.

Flatten the HealthBench JSONL files into one structured index (one record per
example) and emit aggregate corpus statistics.

Inputs  (data/, git-ignored):
    healthbench_full.jsonl        (5000 examples — the superset)
    healthbench_hard.jsonl        (1000)   -> membership flag only
    healthbench_consensus.jsonl   (3671)   -> membership flag only

Outputs:
    data/derived/index.jsonl      one record per example (CONTAINS HealthBench
                                  text -> git-ignored, do not share)
    data/derived/stats.json       aggregate-only stats (safe to share)

Index record schema:
    {
      "example_id":      str,
      "n_turns":         int,
      "last_user_turn":  str,             # the operative user message
      "prompt_text":     str,             # full concatenated conversation
      "themes":          [str],           # from example_tags  "theme:*"
      "phys_categories": [str],           # "physician_agreed_category:*"
      "in_hard":         bool,
      "in_consensus":    bool,
      "n_criteria":      int,
      "axis_counts":     {axis: int},
      "criteria":        [{"text", "points", "axis", "tags"}]
    }
"""
import json
from collections import Counter
from pathlib import Path

DATA = Path("data")
DERIVED = DATA / "derived"


def load(name):
    p = DATA / name
    return [json.loads(l) for l in p.open()] if p.exists() else []


def axis_of(tags):
    for t in tags:
        if t.startswith("axis:"):
            return t.split(":", 1)[1]
    return None


def prefixed(tags, prefix):
    return [t.split(":", 1)[1] for t in tags if t.startswith(prefix)]


def build_record(ex, hard_ids, cons_ids):
    prompt = ex.get("prompt", [])
    user_turns = [t.get("content", "") for t in prompt if t.get("role") == "user"]
    criteria = []
    axis_counts = Counter()
    for r in ex.get("rubrics", []):
        ax = axis_of(r.get("tags", []))
        axis_counts[ax or "none"] += 1
        criteria.append({
            "text": r.get("criterion", ""),
            "points": r.get("points", 0),
            "axis": ax,
            "tags": r.get("tags", []),
        })
    etags = ex.get("example_tags", [])
    return {
        "example_id": ex.get("prompt_id"),
        "n_turns": len(prompt),
        "last_user_turn": user_turns[-1] if user_turns else "",
        "prompt_text": "\n".join(
            f"{t.get('role','?')}: {t.get('content','')}" for t in prompt
        ),
        "themes": prefixed(etags, "theme:"),
        "phys_categories": prefixed(etags, "physician_agreed_category:"),
        "in_hard": ex.get("prompt_id") in hard_ids,
        "in_consensus": ex.get("prompt_id") in cons_ids,
        "n_criteria": len(criteria),
        "axis_counts": dict(axis_counts),
        "criteria": criteria,
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    full = load("healthbench_full.jsonl")
    hard_ids = {e["prompt_id"] for e in load("healthbench_hard.jsonl")}
    cons_ids = {e["prompt_id"] for e in load("healthbench_consensus.jsonl")}

    records = [build_record(e, hard_ids, cons_ids) for e in full]

    with (DERIVED / "index.jsonl").open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # ---- aggregate stats (no example text) ----
    n = len(records)
    ncrit = [r["n_criteria"] for r in records]
    nturns = [r["n_turns"] for r in records]
    axes, themes, cats = Counter(), Counter(), Counter()
    pts = Counter()
    for r in records:
        for k, v in r["axis_counts"].items():
            axes[k] += v
        for t in r["themes"]:
            themes[t] += 1
        for c in r["phys_categories"]:
            cats[c] += 1
        for crit in r["criteria"]:
            pts["negative" if crit["points"] < 0 else "positive" if crit["points"] > 0 else "zero"] += 1

    total_crit = sum(ncrit)
    stats = {
        "n_examples": n,
        "n_hard": sum(r["in_hard"] for r in records),
        "n_consensus": sum(r["in_consensus"] for r in records),
        "n_criteria_total": total_crit,
        "criteria_per_example": {
            "min": min(ncrit), "max": max(ncrit), "mean": round(total_crit / n, 2),
        },
        "turns_per_example": {
            "min": min(nturns), "max": max(nturns), "mean": round(sum(nturns) / n, 2),
            "multi_turn_examples": sum(t > 1 for t in nturns),
        },
        "axis_distribution": {k: [v, round(100 * v / total_crit, 1)] for k, v in axes.most_common()},
        "theme_distribution": dict(themes.most_common()),
        "phys_category_distribution": dict(cats.most_common()),
        "points_sign": dict(pts),
    }
    (DERIVED / "stats.json").write_text(json.dumps(stats, indent=2))

    # ---- console summary ----
    print(f"parsed {n} examples -> {DERIVED/'index.jsonl'}")
    print(f"  hard={stats['n_hard']}  consensus={stats['n_consensus']}")
    print(f"  criteria: total={total_crit}  per-example mean={stats['criteria_per_example']['mean']} "
          f"(min {min(ncrit)}, max {max(ncrit)})")
    print(f"  turns: multi-turn examples={stats['turns_per_example']['multi_turn_examples']} "
          f"(max {max(nturns)})")
    print("  axes:")
    for k, (v, p) in stats["axis_distribution"].items():
        print(f"    {k:<26} {v:6d}  {p:4.1f}%")
    print("  themes:")
    for k, v in themes.most_common():
        print(f"    {k:<26} {v:6d}")
    print("  points sign:", dict(pts))


if __name__ == "__main__":
    main()
