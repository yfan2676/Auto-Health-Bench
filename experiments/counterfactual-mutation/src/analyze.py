#!/usr/bin/env python3
"""Step 7 — score the locality test: footprint precision/recall + off-target rate.

Joins the a-priori footprint prediction with the paired-grading verdicts and reports, over
all (item, criterion) pairs:

  Confusion matrix    predicted (footprint vs kept)  x  actual (changed vs unchanged)
  Footprint precision = TP / (TP + FP)   (of criteria we predicted would move, how many did)
  Footprint recall    = TP / (TP + FN)   (of criteria that moved, how many we predicted)
  OFF-TARGET rate     = FP / (FP + TN)   (bridge criteria that moved — compare to noise floor)
  ON-TARGET  rate     = recall           (footprint criteria that actually moved)

where "positive" = predicted age-sensitive (in the footprint), "actual change" = the fixed
answer's verdict differs between V and V'. A clean, local dimension shows OFF-TARGET ~ the
judge-noise floor and a high ON-TARGET rate. Also breaks the actual change rate down by
rubric axis and by predicted bucket.

Output: results/metrics.json + results/report.md

Usage:
    python3 src/analyze.py
"""
import argparse
import json
from collections import defaultdict

import common


def load_paired():
    rows = []
    if not common.GRADES.exists():
        raise FileNotFoundError(f"{common.GRADES} not found — run src/paired_grade.py first")
    for fp in sorted(common.GRADES.glob("*.jsonl")):
        eid = fp.stem
        for line in fp.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec["example_id"] = eid
            rows.append(rec)
    return rows


def main():
    argparse.ArgumentParser().parse_args()  # no args; keep a consistent CLI shape

    rows = load_paired()
    n = len(rows)
    n_items = len({r["example_id"] for r in rows})

    # Confusion matrix: positive = predicted age_sensitive; actual = changed.
    tp = sum(1 for r in rows if r["age_sensitive"] and r["changed"])
    fn = sum(1 for r in rows if r["age_sensitive"] and not r["changed"])
    fp = sum(1 for r in rows if not r["age_sensitive"] and r["changed"])
    tn = sum(1 for r in rows if not r["age_sensitive"] and not r["changed"])

    def safe(a, b):
        return (a / b) if b else None

    precision = safe(tp, tp + fp)
    recall = safe(tp, tp + fn)
    off_target = safe(fp, fp + tn)     # bridge criteria that moved
    on_target = recall                 # footprint criteria that moved
    f1 = safe(2 * precision * recall, precision + recall) if precision and recall else None

    # Breakdowns.
    by_axis = defaultdict(lambda: [0, 0])      # axis -> [changed, total]
    by_bucket = defaultdict(lambda: [0, 0])    # predicted bucket -> [changed, total]
    for r in rows:
        ax = r.get("axis") or "untagged"
        by_axis[ax][0] += r["changed"]; by_axis[ax][1] += 1
        b = r["predicted_bucket"]
        by_bucket[b][0] += r["changed"]; by_bucket[b][1] += 1

    floor = None
    floor_p = common.RESULTS / "noise_floor.json"
    if floor_p.exists():
        floor = json.loads(floor_p.read_text()).get("flip_rate")

    metrics = {
        "n_items": n_items, "n_criteria_pairs": n,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "footprint_precision": precision, "footprint_recall": recall, "footprint_f1": f1,
        "off_target_change_rate": off_target, "on_target_change_rate": on_target,
        "judge_noise_floor": floor,
        "actual_change_rate_by_axis": {k: {"rate": safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_axis.items())},
        "actual_change_rate_by_predicted_bucket": {k: {"rate": safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_bucket.items())},
    }
    common.atomic_write_json(common.RESULTS / "metrics.json", metrics)

    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    lines = [
        "# Counterfactual age-locality — E1 results", "",
        f"- items: **{n_items}**, criterion-pairs graded: **{n}**",
        f"- judge-noise floor (identical-input flip rate): **{pct(floor)}**",
        "",
        "## Locality (the headline)", "",
        f"- **OFF-TARGET change rate** (bridge criteria that moved): **{pct(off_target)}**  "
        f"← compare to noise floor {pct(floor)}; near it ⇒ the bridge holds.",
        f"- **ON-TARGET change rate** (footprint criteria that moved): **{pct(on_target)}**",
        f"- footprint precision **{pct(precision)}**, recall **{pct(recall)}**, F1 **{pct(f1)}**",
        "",
        "## Confusion matrix (predicted × actual)", "",
        "| | actual: changed | actual: unchanged |",
        "|---|---|---|",
        f"| predicted footprint | {tp} (TP) | {fn} (FN) |",
        f"| predicted kept (bridge) | {fp} (FP) | {tn} (TN) |",
        "",
        "## Actual change rate by rubric axis", "",
        "| axis | change rate | n |", "|---|---|---|",
    ]
    for k, v in metrics["actual_change_rate_by_axis"].items():
        lines.append(f"| {k} | {pct(v['rate'])} | {v['n']} |")
    lines += ["", "## Actual change rate by predicted bucket", "",
              "| predicted bucket | change rate | n |", "|---|---|---|"]
    for k, v in metrics["actual_change_rate_by_predicted_bucket"].items():
        lines.append(f"| {k} | {pct(v['rate'])} | {v['n']} |")
    lines += ["", "_Generated by src/analyze.py. Interpretation: a clean, local dimension has "
              "OFF-TARGET ≈ noise floor and a high ON-TARGET rate; a high OFF-TARGET rate means "
              "the age edit rippled beyond the predicted footprint (or the prediction was poor)._"]
    (common.RESULTS / "report.md").write_text("\n".join(lines) + "\n")

    print(f"items={n_items} pairs={n}  off_target={pct(off_target)} (floor {pct(floor)})  "
          f"on_target={pct(on_target)}  precision={pct(precision)} recall={pct(recall)}")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


if __name__ == "__main__":
    main()
