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


def _load_footprint_preds():
    """{example_id: {idx: prediction}} from results/footprint/*.json.

    The a-priori footprint prediction is the SOURCE OF TRUTH for predicted_bucket /
    predicted_sensitive (same as src/build_viewer.py reads). sweep_grade.py snapshots a copy
    into each grade row, but that snapshot is "kept" whenever the footprint step had not yet run
    at grade time — so we re-join the live footprint files here and let it win, which lets the
    footprint step be run (or re-run) after grading without re-grading anything.
    """
    out = {}
    if common.FOOTPRINT.exists():
        for fp in common.FOOTPRINT.glob("*.json"):
            try:
                rec = json.loads(fp.read_text())
            except json.JSONDecodeError:
                continue
            out[fp.stem] = {p["idx"]: p for p in rec.get("predictions", [])}
    return out


def _load_dir(path, fp_preds):
    rows = []
    for fp in sorted(path.glob("*.jsonl")):
        eid = fp.stem
        preds = fp_preds.get(eid, {})
        for line in fp.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec["example_id"] = eid
            # Prefer the live footprint prediction over the snapshot baked into the grade row.
            p = preds.get(rec.get("idx"))
            if p is not None:
                rec["predicted_bucket"] = p.get("bucket", "kept")
                rec["predicted_sensitive"] = bool(
                    p.get("predicted_sensitive", p.get("bucket", "kept") != "kept"))
            rows.append(_normalize(rec))
    return rows


def load_rows():
    """Load the measured sweep grades (the behavioral footprint), joined with the live
    a-priori footprint predictions (results/footprint/)."""
    if common.SWEEP_GRADES.exists() and any(common.SWEEP_GRADES.glob("*.jsonl")):
        return _load_dir(common.SWEEP_GRADES, _load_footprint_preds()), "sweep_grades"
    raise FileNotFoundError(
        f"no grades found — run src/sweep_grade.py first (looked in {common.SWEEP_GRADES})")


def _safe(a, b):
    return (a / b) if b else None


def confusion_metrics(rows):
    # Positive = predicted dimension-sensitive (in the footprint); actual positive = the
    # criterion's verdict actually moved across the sweep. Standard confusion orientation.
    tp = sum(1 for r in rows if r["predicted_sensitive"] and r["changed"])        # predicted move, moved
    fp = sum(1 for r in rows if r["predicted_sensitive"] and not r["changed"])    # predicted move, held (false alarm)
    fn = sum(1 for r in rows if not r["predicted_sensitive"] and r["changed"])    # moved, predicted bridge (off-target)
    tn = sum(1 for r in rows if not r["predicted_sensitive"] and not r["changed"])
    precision = _safe(tp, tp + fp)   # of criteria predicted to move, how many did = on-target change rate
    recall = _safe(tp, tp + fn)      # of criteria that moved, how many we predicted
    f1 = _safe(2 * precision * recall, precision + recall) if precision and recall else None
    return {
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "change_rate": _safe(tp + fn, tp + fp + fn + tn),  # any criterion whose verdict moved
        "footprint_precision": precision, "footprint_recall": recall, "footprint_f1": f1,
        "off_target_change_rate": _safe(fn, fn + tn),  # bridge (predicted-kept) criteria that moved
        "on_target_change_rate": precision,            # footprint (predicted-sensitive) criteria that moved
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
    floor_p = common.NOISE_FLOOR
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

    def pdelta(x):  # net effect is a delta of two rates; show as a signed %
        return "n/a" if x is None else f"{x*100:+.1f}%"

    floor_line = ", ".join(f"{d} **{pct(v)}**" for d, v in sorted(floor_by_dim.items())) or "n/a"

    # Footprint-discrimination summary, data-driven so the prose matches whatever classifier model
    # produced results/footprint_*/ (the dir is versioned + selectable via CM_FOOTPRINT_DIR).
    fp_model = common.FOOTPRINT.name.replace("footprint_", "") or common.FOOTPRINT.name
    _on = overall["on_target_change_rate"] or 0.0
    _off = overall["off_target_change_rate"] or 0.0
    _gap = _on - _off
    _conf = overall["confusion"]
    _tot = sum(_conf.values()) or 1
    _flag_share = (_conf["tp"] + _conf["fp"]) / _tot
    if _gap >= 0.08:
        _disc = "clearly positive"
    elif _gap >= 0.03:
        _disc = "weakly positive"
    elif _gap > -0.03:
        _disc = "near chance"
    else:
        _disc = "inverted (below chance)"

    # Flag an incomplete run (e.g. a dimension whose same-input floor has not been measured yet, as
    # happens if the run was interrupted) so an n/a net effect reads as "pending", not "no signal".
    _missing_floor = [d for d, m in by_dimension.items() if m.get("same_input_floor") is None]
    _partial = ([f"> ⚠ **Partial run** — same-input floor not yet measured for "
                 f"**{', '.join(_missing_floor)}** (net effect below shows n/a there; fill it with "
                 f"`noise_floor.py --dimension <d>`). The raw change-rate, by-axis and "
                 f"footprint-discrimination numbers ARE complete.", ""]
                if _missing_floor else [])

    lines = [
        "# Counterfactual dimensional locality — results", "",
        f"- items: **{n_items}**, criterion-pairs graded: **{n}**",
        f"- same-input floor (per dimension): {floor_line}",
        "",
        *_partial,
        "## Headline", "",
        "> Answers to V and to each V_k are sampled independently, so the raw change rate includes the"
        " model's roll-to-roll answer variance. The dimension signal is **net = change rate − same-input"
        " floor** (per dimension). See the by-dimension table.",
        "",
        f"- **raw change rate** (any criterion whose verdict moved across the sweep): **{pct(overall['change_rate'])}**",
        f"- **footprint discrimination ({fp_model}) is {_disc}**: predicted-sensitive criteria moved "
        f"**{pct(_on)}** (on-target) vs predicted-bridge **{pct(_off)}** (off-target) — a **{_gap*100:+.1f}-pt** gap, "
        f"flagging **{_flag_share:.1%}** of criteria. Footprint precision **{pct(overall['footprint_precision'])}**, "
        f"recall **{pct(overall['footprint_recall'])}** (see caveat below).",
        "",
        "## By dimension (net effect vs the same-input floor)", "",
        "| dimension | items | raw change rate | same-input floor | **net effect (Δ)** |",
        "|---|---|---|---|---|",
    ]
    for d, m in by_dimension.items():
        lines.append(f"| {d} | {m['n_items']} | {pct(m['change_rate'])} | "
                     f"{pct(m.get('same_input_floor'))} | **{pdelta(m.get('net_dimension_effect'))}** |")
    lines += ["", "## Footprint discrimination by dimension "
              "(does predicted-sensitive move more than the predicted bridge?)", "",
              "| dimension | on-target (pred-sensitive moved) | off-target (bridge moved) | recall (of moved, predicted) |",
              "|---|---|---|---|"]
    for d, m in by_dimension.items():
        lines.append(f"| {d} | {pct(m['on_target_change_rate'])} | {pct(m['off_target_change_rate'])} | "
                     f"{pct(m['footprint_recall'])} |")
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
              f"- **A-priori footprint classifier ({fp_model}) discrimination is {_disc}.** It flags "
              f"**{_flag_share:.1%}** of criteria as sensitive; those move **{pct(_on)}** (on-target) vs "
              f"**{pct(_off)}** for the predicted bridge (off-target), a **{_gap*100:+.1f}-pt** gap. A clearly "
              "positive gap means the a-priori prediction adds signal over the behavioral sweep; a ≈0 or negative "
              "gap means it does not, and the reliable footprint signal is then the measured per-axis change rate "
              "and by-value flip distribution rather than the predicted buckets. The footprint model is versioned "
              "(results/footprint_v*/) and selectable via CM_FOOTPRINT_DIR; the net-effect headline above is "
              "computed from the behavioral sweep alone and does NOT change with the classifier model.",
              f"- **The same-input floor ({floor_line}) is high** because the answer model at temperature "
              "varies run-to-run; with it subtracted the net dimension effect is modest. Lower answer "
              "temperature or averaging several answers per input would raise signal-to-noise.",
              "",
              "_Generated by src/analyze.py. Interpretation: net effect = change rate − same-input floor. "
              "A clean, local dimension shows a small positive net concentrated in the dimension-relevant "
              "criteria; ≈0 net means the bridge holds (the edit did not change the model's "
              "clinically-graded behavior beyond its own sampling noise)._"]
    (common.RESULTS / "report.md").write_text("\n".join(lines) + "\n")

    net_str = ", ".join(f"{d} {pdelta(m.get('net_dimension_effect'))}" for d, m in by_dimension.items())
    print(f"source={source} items={n_items} pairs={n}  "
          f"raw_change={pct(overall['change_rate'])}  net[{net_str}]")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


if __name__ == "__main__":
    main()
