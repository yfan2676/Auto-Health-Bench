#!/usr/bin/env python3
"""Step 7 — score the locality test: change rate, net dimension effect, footprint P/R.

Joins the a-priori footprint prediction with the measured K-value sweep verdicts
(results/sweep_grades/, src/sweep_grade.py) and reports, over all (item, criterion) pairs:

  Confusion matrix    predicted (footprint vs kept)  x  actual (changed vs unchanged)
  Footprint precision = TP / (TP + FP)   (of criteria we predicted would move, how many did)
  Footprint recall    = TP / (TP + FN)   (of criteria that moved, how many we predicted)

where "positive" = predicted dimension-sensitive (in the footprint) and "actual change" = the
model's fresh answer to V_k satisfies the criterion differently than its fresh answer to V.

Because the answers to V and each V_k are independently sampled, the raw change rate includes
the model's roll-to-roll answer variance. The honest signal is the NET effect:
`net = change rate − same-input floor` (the floor is measured per dimension by
src/noise_floor.py). Breakdowns: change rate by rubric axis, by predicted bucket, by DIMENSION
(D1 age / D2 disclosure), and the sweep flip-point distribution.

Output: results/metrics.json + results/report.md

Usage:
    python3 src/analyze.py
"""
import argparse
import json
from collections import Counter, defaultdict

import common


def _normalize(rec):
    """Map a sweep grade row to a common shape used by the metrics below."""
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
    """Load the measured sweep grades (the behavioral footprint)."""
    if common.SWEEP_GRADES.exists() and any(common.SWEEP_GRADES.glob("*.jsonl")):
        return _load_dir(common.SWEEP_GRADES), "sweep_grades"
    raise FileNotFoundError(
        f"no grades found — run src/sweep_grade.py first (looked in {common.SWEEP_GRADES})")


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
        "change_rate": _safe(tp + fp, tp + fp + fn + tn),  # any criterion whose verdict moved
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

    # Same-input floor (per dimension, src/noise_floor.py): the flip rate from re-sampling the
    # model's answer to the SAME input. The change rate compares independently sampled answers
    # to V vs V_k, so this baseline — the model's own roll-to-roll answer variance — is
    # subtracted to get the net dimension effect = change rate − floor.
    floor_by_dim = {}
    floor_p = common.RESULTS / "noise_floor.json"
    if floor_p.exists():
        for d, rec in (json.loads(floor_p.read_text()).get("by_dimension") or {}).items():
            floor_by_dim[d] = rec.get("flip_rate")

    for d, m in by_dimension.items():
        f_d = floor_by_dim.get(d)
        raw = m["change_rate"]
        m["same_input_floor"] = f_d
        m["net_dimension_effect"] = (raw - f_d) if (raw is not None and f_d is not None) else None

    metrics = {
        "source": source, "n_items": n_items, "n_criteria_pairs": n,
        **overall,
        "same_input_floor_by_dimension": floor_by_dim,
        "by_dimension": by_dimension,
        "actual_change_rate_by_axis": {k: {"rate": _safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_axis.items())},
        "actual_change_rate_by_predicted_bucket": {k: {"rate": _safe(v[0], v[1]), "n": v[1]} for k, v in sorted(by_bucket.items())},
        "flip_point_distribution": dict(sorted(flip_points.items(), key=lambda kv: (len(kv[0]), kv[0]))),
    }
    common.atomic_write_json(common.RESULTS / "metrics.json", metrics)

    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    def ppts(x):
        return "n/a" if x is None else f"{x*100:+.1f} pts"

    floor_line = ", ".join(f"{d} **{pct(v)}**" for d, v in sorted(floor_by_dim.items())) or "n/a"
    lines = [
        "# Counterfactual dimensional locality — results", "",
        f"- items: **{n_items}**, criterion-pairs graded: **{n}**",
        f"- same-input floor (per dimension): {floor_line}",
        "",
        "## Headline", "",
        "> Answers to V and to each V_k are sampled independently, so the raw change rate includes the"
        " model's roll-to-roll answer variance. The dimension signal is **net = change rate − same-input"
        " floor** (per dimension). See the by-dimension table.",
        "",
        f"- **raw change rate** (any criterion whose verdict moved across the sweep): **{pct(overall['change_rate'])}**",
        f"- footprint precision **{pct(overall['footprint_precision'])}**, recall **{pct(overall['footprint_recall'])}** "
        f"(the a-priori Qwen-4B classifier predicts ~0 sensitive — see caveat below).",
        "",
        "## By dimension (net effect vs the same-input floor)", "",
        "| dimension | items | raw change rate | same-input floor | **net effect** |",
        "|---|---|---|---|---|",
    ]
    for d, m in by_dimension.items():
        lines.append(f"| {d} | {m['n_items']} | {pct(m['change_rate'])} | "
                     f"{pct(m.get('same_input_floor'))} | **{ppts(m.get('net_dimension_effect'))}** |")
    lines += ["", "## Change rate by rubric axis", "",
              "| axis | change rate | n |", "|---|---|---|"]
    for k, v in metrics["actual_change_rate_by_axis"].items():
        lines.append(f"| {k} | {pct(v['rate'])} | {v['n']} |")
    if metrics["flip_point_distribution"]:
        lines += ["", "## Sweep flip-point distribution (criteria that flipped, by value)", "",
                  "| value | # criteria flipped |", "|---|---|"]
        for k, v in metrics["flip_point_distribution"].items():
            lines.append(f"| {k} | {v} |")
    lines += ["", "## Caveats", "",
              "- **The a-priori footprint classifier is degenerate on Qwen3-4B** (predicts ~0 sensitive "
              "criteria), so footprint precision/recall collapse. The usable footprint signal is the "
              "measured per-axis change rate and the by-value flip distribution, not the predicted buckets.",
              "- **The same-input floor is high (~24%)** because a 4B answer model at temperature varies "
              "a lot run-to-run; with it subtracted the net dimension effect is modest. Lower answer "
              "temperature or averaging several answers per input would raise signal-to-noise.",
              "",
              "_Generated by src/analyze.py. Interpretation: net effect = change rate − same-input floor. "
              "A clean, local dimension shows a small positive net concentrated in the dimension-relevant "
              "criteria; ≈0 net means the bridge holds (the edit did not change the model's "
              "clinically-graded behavior beyond its own sampling noise)._"]
    (common.RESULTS / "report.md").write_text("\n".join(lines) + "\n")

    net_str = ", ".join(f"{d} {ppts(m.get('net_dimension_effect'))}" for d, m in by_dimension.items())
    print(f"source={source} items={n_items} pairs={n}  "
          f"raw_change={pct(overall['change_rate'])}  net[{net_str}]")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


if __name__ == "__main__":
    main()
