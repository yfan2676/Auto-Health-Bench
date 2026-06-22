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
import statistics
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


def _item_input_scores(rows):
    """For one item's raw sweep_grades rows, return (sd, scores): `scores` maps each input label
    ("V" and each variant value) to its HealthBench per-answer score (common.rubric_score), and `sd`
    is the std-dev of those scores ACROSS inputs. Only criteria graded on V and on every variant are
    used, so all inputs are scored over an identical criterion set. (None, {}) if <2 scorable inputs.
    """
    values = []
    for r in rows:
        for c in r.get("sweep", []):
            if c["value"] not in values:
                values.append(c["value"])

    def cell(r, v):
        return next((c for c in r.get("sweep", []) if c["value"] == v), None)

    usable = [r for r in rows
              if r.get("verdict_orig") is not None and all(cell(r, v) is not None for v in values)]
    if not usable:
        return None, {}
    scores = {"V": common.rubric_score(
        [{"points": r["points"], "criteria_met": bool(r["verdict_orig"])} for r in usable])}
    for v in values:
        scores[v] = common.rubric_score(
            [{"points": r["points"], "criteria_met": bool(cell(r, v)["verdict"])} for r in usable])
    vals = [s for s in scores.values() if s is not None]
    return (statistics.stdev(vals) if len(vals) >= 2 else None), scores


def score_variation_by_dimension(dim_of):
    """Mean over items (per dimension) of the per-item across-input score SD — the dimension sweep's
    score variation, read from the raw sweep_grades files (same source as the change rate). Returns
    {dimension: (mean_sd, n_items)}."""
    by_dim = defaultdict(list)
    if common.SWEEP_GRADES.exists():
        for fp in sorted(common.SWEEP_GRADES.glob("*.jsonl")):
            rows = []
            for line in fp.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            sd, _ = _item_input_scores(rows)
            if sd is not None:
                by_dim[dim_of.get(fp.stem, "age")].append(sd)
    return {d: (sum(v) / len(v), len(v)) for d, v in by_dim.items()}


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
    floor_by_dim = {}          # legacy per-criterion flip-rate floor (per dimension)
    floor_sd_by_dim = {}       # same-input answer-score std-dev floor (per dimension) — the headline
    floor_p = common.NOISE_FLOOR
    if floor_p.exists():
        for d, rec in (json.loads(floor_p.read_text()).get("by_dimension") or {}).items():
            floor_by_dim[d] = rec.get("flip_rate")
            floor_sd_by_dim[d] = rec.get("score_sd")

    for d, m in by_dimension.items():
        f_d = floor_by_dim.get(d)
        raw = m["change_rate"]
        m["same_input_floor"] = f_d
        m["net_dimension_effect"] = (raw - f_d) if (raw is not None and f_d is not None) else None

    # HEADLINE metric: run-to-run std-dev of the HealthBench answer SCORE. The sweep's per-dimension
    # score SD (spread of the score across V + its variants) minus the same-input floor SD (spread
    # across K resamples of V) is the net score effect of mutating the dimension. The sweep side is
    # computed live from sweep_grades; the floor side comes from noise_floor.py's score_sd (needs a
    # run to populate — older floor files only carry the legacy flip_rate).
    sweep_sd = score_variation_by_dimension(dim_of)        # {dim: (mean_sd, n_items)}
    score_var_by_dim = {}
    for d in sorted(set(sweep_sd) | set(floor_sd_by_dim) | set(by_dimension)):
        s = sweep_sd.get(d, (None, 0))[0]
        f = floor_sd_by_dim.get(d)
        score_var_by_dim[d] = {
            "sweep_score_sd": s,
            "same_input_floor_sd": f,
            "net_score_sd": (s - f) if (s is not None and f is not None) else None,
            "n_items": sweep_sd.get(d, (None, 0))[1],
        }

    metrics = {
        "source": source, "n_items": n_items, "n_criteria_pairs": n,
        **overall,
        "same_input_floor_by_dimension": floor_by_dim,
        "score_variation_by_dimension": score_var_by_dim,
        "same_input_floor_sd_by_dimension": floor_sd_by_dim,
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

    # The headline floor is the same-input SCORE std-dev (per dimension); the legacy flip-rate floor
    # still appears in the per-criterion view below.
    floor_sd_line = ", ".join(f"{d} **{pct(v)}**" for d, v in sorted(floor_sd_by_dim.items())
                              if v is not None) or "n/a (run noise_floor.py)"

    # Footprint-discrimination summary (per-CRITERION view), data-driven so the prose matches whatever
    # classifier model produced results/footprint_*/ (versioned + selectable via CM_FOOTPRINT_DIR).
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

    # Flag an incomplete run: any dimension whose same-input SCORE floor has not been measured yet
    # (run interrupted, or the floor file predates this metric) so an n/a net reads "pending".
    _missing_floor = [d for d, m in score_var_by_dim.items() if m.get("same_input_floor_sd") is None]
    _partial = ([f"> ⚠ **Partial run** — same-input score floor not yet measured for "
                 f"**{', '.join(_missing_floor)}** (net score SD shows n/a there; fill it by running "
                 f"`noise_floor.py`). The sweep score SD and the per-criterion view ARE complete.", ""]
                if _missing_floor else [])

    lines = [
        "# Counterfactual dimensional locality — results", "",
        f"- items: **{n_items}**, criterion-pairs graded: **{n}**",
        f"- same-input floor — answer-score std-dev (per dimension): {floor_sd_line}",
        "",
        *_partial,
        "## Headline — dimension effect on the answer score", "",
        "> Each answer is scored with the HealthBench rubric (achieved ÷ total possible points). The"
        " dimension signal is the run-to-run **std-dev of that score**: the spread across V and its"
        " mutated variants (the sweep) minus the spread across K fresh answers to the SAME input (the"
        " same-input floor). **net score SD = sweep score SD − floor score SD** (per dimension), in"
        " score points (a 0–100% rubric score).",
        "",
        "| dimension | items | sweep score SD | same-input floor SD | **net score SD (Δ)** |",
        "|---|---|---|---|---|",
    ]
    for d, m in score_var_by_dim.items():
        lines.append(f"| {d} | {m['n_items']} | {pct(m['sweep_score_sd'])} | "
                     f"{pct(m.get('same_input_floor_sd'))} | **{pdelta(m.get('net_score_sd'))}** |")
    lines += [
        "",
        "## Per-criterion view (which criteria move + footprint discrimination)", "",
        "> The numbers below are per-criterion verdict **flips** (an answer satisfies a criterion"
        " differently across inputs) — NOT score-weighted. They drive the a-priori footprint"
        " classifier's precision/recall; the score-SD headline above is the score-weighted summary.",
        "",
        f"- **raw change rate** (any criterion whose verdict moved across the sweep): **{pct(overall['change_rate'])}**",
        f"- **footprint discrimination ({fp_model}) is {_disc}**: predicted-sensitive criteria moved "
        f"**{pct(_on)}** (on-target) vs predicted-bridge **{pct(_off)}** (off-target) — a **{_gap*100:+.1f}-pt** gap, "
        f"flagging **{_flag_share:.1%}** of criteria. Footprint precision **{pct(overall['footprint_precision'])}**, "
        f"recall **{pct(overall['footprint_recall'])}**.",
        "",
        "| dimension | items | raw change rate | legacy flip-rate floor | on-target | off-target |",
        "|---|---|---|---|---|---|",
    ]
    for d, m in by_dimension.items():
        lines.append(f"| {d} | {m['n_items']} | {pct(m['change_rate'])} | {pct(m.get('same_input_floor'))} | "
                     f"{pct(m['on_target_change_rate'])} | {pct(m['off_target_change_rate'])} |")
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
              f"- **The same-input score floor ({floor_sd_line}) is the model's own roll-to-roll score"
              " variance** — answers to the SAME input, sampled at temperature, score differently. The net"
              " score SD subtracts it, so it is the score movement attributable to the dimension beyond that"
              " noise. Lower the answer temperature or average several answers per input to shrink the floor.",
              f"- **A-priori footprint classifier ({fp_model}) discrimination is {_disc}** (per-criterion). It"
              f" flags **{_flag_share:.1%}** of criteria as sensitive; those move **{pct(_on)}** (on-target) vs "
              f"**{pct(_off)}** for the predicted bridge (off-target), a **{_gap*100:+.1f}-pt** gap. The footprint"
              " model is versioned (results/footprint_v*/) and selectable via CM_FOOTPRINT_DIR; neither headline"
              " changes with the classifier model.",
              "",
              "_Generated by src/analyze.py. Headline: net score SD = sweep score SD − same-input floor SD."
              " A local dimension shows a small positive net concentrated in the dimension-relevant criteria;"
              " ≈0 net means the bridge holds (mutating the dimension did not move the rubric score beyond the"
              " model's own sampling noise)._"]
    (common.RESULTS / "report.md").write_text("\n".join(lines) + "\n")

    net_str = ", ".join(f"{d} {pdelta(m.get('net_score_sd'))}" for d, m in score_var_by_dim.items())
    sweep_str = ", ".join(f"{d} {pct(m.get('sweep_score_sd'))}" for d, m in score_var_by_dim.items())
    print(f"source={source} items={n_items} pairs={n}  sweep_scoreSD[{sweep_str}]  net_scoreSD[{net_str}]")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


if __name__ == "__main__":
    main()
