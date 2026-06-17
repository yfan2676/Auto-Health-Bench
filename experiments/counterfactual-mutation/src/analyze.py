#!/usr/bin/env python3
"""Step 7 — score the locality test: footprint precision/recall + off-target rate.

Joins the a-priori footprint prediction with the measured paired/sweep verdicts and
reports, over all (item, criterion) pairs:

  Confusion matrix    predicted (footprint vs kept)  x  actual (changed vs unchanged)
  Footprint precision = TP / (TP + FP)   (of criteria we predicted would move, how many did)
  Footprint recall    = TP / (TP + FN)   (of criteria that moved, how many we predicted)
  OFF-TARGET rate     = FP / (FP + TN)   (bridge criteria that moved — compare to noise floor)
  ON-TARGET  rate     = recall           (footprint criteria that actually moved)

where "positive" = predicted dimension-sensitive (in the footprint), "actual change" = the
fixed answer's verdict differs between V and the edited conversation(s). A clean, local
dimension shows OFF-TARGET ~ the judge-noise floor and a high ON-TARGET rate.

Input preference: the K-value SWEEP (results/sweep_grades/, src/sweep_grade.py) — the
behavioral footprint — if present; else the legacy single-edit paired grades
(results/grades/, src/paired_grade.py). Breakdowns: actual change rate by rubric axis, by
predicted bucket, by DIMENSION (D1 age / D2 disclosure), and the sweep flip-point
distribution. The predicted-vs-measured agreement (precision/recall + accuracy) is E1b's
headline: does the cheap a-priori classifier match the behavioral truth?

Output: results/metrics.json + results/report.md

Usage:
    python3 src/analyze.py
"""
import argparse
import json
from collections import Counter, defaultdict

import common


def _normalize(rec):
    """Map a sweep or legacy grade row to a common shape used by the metrics below."""
    bucket = rec.get("predicted_bucket", "kept")
    sensitive = rec.get("predicted_sensitive", rec.get("age_sensitive", bucket != "kept"))
    return {
        "example_id": rec.get("example_id"),
        "idx": rec.get("idx"),
        "axis": rec.get("axis") or "untagged",
        "predicted_bucket": bucket,
        "predicted_sensitive": bool(sensitive),
        "changed": bool(rec.get("changed")),
        "flip_values": rec.get("flip_values", []),
    }


def _load_dir(path):
    rows = []
    for fp in sorted(path.glob("*.jsonl")):
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
            rows.append(_normalize(rec))
    return rows


def load_rows():
    """Prefer the sweep grades (behavioral footprint); fall back to legacy paired grades."""
    if common.SWEEP_GRADES.exists() and any(common.SWEEP_GRADES.glob("*.jsonl")):
        return _load_dir(common.SWEEP_GRADES), "sweep_grades"
    if common.GRADES.exists() and any(common.GRADES.glob("*.jsonl")):
        return _load_dir(common.GRADES), "grades"
    raise FileNotFoundError(
        f"no grades found — run src/sweep_grade.py (or src/paired_grade.py) first "
        f"(looked in {common.SWEEP_GRADES} and {common.GRADES})")


def _safe(a, b):
    return (a / b) if b else None


def confusion_metrics(rows):
    tp = sum(1 for r in rows if r["predicted_sensitive"] and r["changed"])
    fn = sum(1 for r in rows if r["predicted_sensitive"] and not r["changed"])
    fp = sum(1 for r in rows if not r["predicted_sensitive"] and r["changed"])
    tn = sum(1 for r in rows if not r["predicted_sensitive"] and not r["changed"])
    precision = _safe(tp, tp + fp)
    recall = _safe(tp, tp + fn)
    f1 = _safe(2 * precision * recall, precision + recall) if precision and recall else None
    return {
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "footprint_precision": precision, "footprint_recall": recall, "footprint_f1": f1,
        "off_target_change_rate": _safe(fp, fp + tn),  # bridge criteria that moved
        "on_target_change_rate": recall,               # footprint criteria that moved
        "predicted_vs_measured_accuracy": _safe(tp + tn, tp + fp + fn + tn),
    }


def main():
    argparse.ArgumentParser().parse_args()  # no args; keep a consistent CLI shape

    rows, source = load_rows()
    n = len(rows)
    n_items = len({r["example_id"] for r in rows})

    # Dimension per example (from the shortlist; default age for legacy runs).
    dim_of = {}
    try:
        for s in common.load_shortlist():
            dim_of[s["example_id"]] = s.get("dimension", "age")
    except FileNotFoundError:
        pass

    overall = confusion_metrics(rows)

    # Breakdowns: change rate by axis and by predicted bucket.
    by_axis = defaultdict(lambda: [0, 0])
    by_bucket = defaultdict(lambda: [0, 0])
    flip_points = Counter()
    for r in rows:
        by_axis[r["axis"]][0] += r["changed"]; by_axis[r["axis"]][1] += 1
        b = r["predicted_bucket"]
        by_bucket[b][0] += r["changed"]; by_bucket[b][1] += 1
        for v in r["flip_values"]:
            flip_points[str(v)] += 1

    # Per-dimension confusion metrics.
    rows_by_dim = defaultdict(list)
    for r in rows:
        rows_by_dim[dim_of.get(r["example_id"], "age")].append(r)
    by_dimension = {d: {**confusion_metrics(rs), "n_criteria_pairs": len(rs),
                        "n_items": len({x['example_id'] for x in rs})}
                    for d, rs in sorted(rows_by_dim.items())}

    floor = None
    floor_p = common.RESULTS / "noise_floor.json"
    if floor_p.exists():
        floor = json.loads(floor_p.read_text()).get("flip_rate")

    metrics = {
        "source": source, "n_items": n_items, "n_criteria_pairs": n,
        **overall,
        "judge_noise_floor": floor,
        "by_dimension": by_dimension,
        "actual_change_rate_by_axis": {k: {"rate": _safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_axis.items())},
        "actual_change_rate_by_predicted_bucket": {k: {"rate": _safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_bucket.items())},
        "flip_point_distribution": dict(sorted(flip_points.items(), key=lambda kv: (len(kv[0]), kv[0]))),
    }
    common.atomic_write_json(common.RESULTS / "metrics.json", metrics)

    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    c = overall["confusion"]
    lines = [
        "# Counterfactual dimensional locality — results", "",
        f"- source: **{source}**  (sweep = behavioral K-value footprint; grades = single edit)",
        f"- items: **{n_items}**, criterion-pairs graded: **{n}**",
        f"- judge-noise floor (identical-input flip rate): **{pct(floor)}**",
        "",
        "## Locality (the headline)", "",
        f"- **OFF-TARGET change rate** (bridge criteria that moved): **{pct(overall['off_target_change_rate'])}**  "
        f"← compare to noise floor {pct(floor)}; near it ⇒ the bridge holds.",
        f"- **ON-TARGET change rate** (footprint criteria that moved): **{pct(overall['on_target_change_rate'])}**",
        f"- footprint precision **{pct(overall['footprint_precision'])}**, recall **{pct(overall['footprint_recall'])}**, "
        f"F1 **{pct(overall['footprint_f1'])}**",
        f"- predicted-vs-measured agreement (accuracy): **{pct(overall['predicted_vs_measured_accuracy'])}**",
        "",
        "## Confusion matrix (predicted × actual)", "",
        "| | actual: changed | actual: unchanged |",
        "|---|---|---|",
        f"| predicted footprint | {c['tp']} (TP) | {c['fn']} (FN) |",
        f"| predicted kept (bridge) | {c['fp']} (FP) | {c['tn']} (TN) |",
        "",
        "## By dimension", "",
        "| dimension | items | off-target | on-target | precision | recall |",
        "|---|---|---|---|---|---|",
    ]
    for d, m in by_dimension.items():
        lines.append(f"| {d} | {m['n_items']} | {pct(m['off_target_change_rate'])} | "
                     f"{pct(m['on_target_change_rate'])} | {pct(m['footprint_precision'])} | "
                     f"{pct(m['footprint_recall'])} |")
    lines += ["", "## Actual change rate by rubric axis", "",
              "| axis | change rate | n |", "|---|---|---|"]
    for k, v in metrics["actual_change_rate_by_axis"].items():
        lines.append(f"| {k} | {pct(v['rate'])} | {v['n']} |")
    lines += ["", "## Actual change rate by predicted bucket", "",
              "| predicted bucket | change rate | n |", "|---|---|---|"]
    for k, v in metrics["actual_change_rate_by_predicted_bucket"].items():
        lines.append(f"| {k} | {pct(v['rate'])} | {v['n']} |")
    if metrics["flip_point_distribution"]:
        lines += ["", "## Sweep flip-point distribution (criteria that flipped, by value)", "",
                  "| value | # criteria flipped |", "|---|---|"]
        for k, v in metrics["flip_point_distribution"].items():
            lines.append(f"| {k} | {v} |")
    lines += ["", "_Generated by src/analyze.py. Interpretation: a clean, local dimension has "
              "OFF-TARGET ≈ noise floor and a high ON-TARGET rate; a high OFF-TARGET rate means "
              "the edit rippled beyond the predicted footprint (or the prediction was poor)._"]
    (common.RESULTS / "report.md").write_text("\n".join(lines) + "\n")

    print(f"source={source} items={n_items} pairs={n}  "
          f"off_target={pct(overall['off_target_change_rate'])} (floor {pct(floor)})  "
          f"on_target={pct(overall['on_target_change_rate'])}  "
          f"precision={pct(overall['footprint_precision'])} recall={pct(overall['footprint_recall'])}")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


if __name__ == "__main__":
    main()
