#!/usr/bin/env python3
"""Step 5 — build the static viewer bundle (viewer/data.json) for this experiment.

For each selected sample it joins: the chosen mutated input (results/sweep/<eid>.json), the
CR_RUNS original + CR_RUNS mutated answers (results/answers_*/<eid>.json), the per-criterion
verdicts for all runs (results/grades_*/<eid>.jsonl), and the per-sample / per-dimension scores
and significance (results/metrics.json). Word-level diff spans between the original and the
single mutated input are precomputed with difflib so the HTML stays dependency-free.

There is no footprint / confusion (TP/FP/FN/TN) / precision-recall here: this experiment asks
whether the mutation moves the overall score, replicated for significance, not which criteria
flip. The viewer shows the original vs mutated input, all 2*CR_RUNS answers, a per-criterion
verdict grid across the runs, and the per-sample + per-dimension significance summary.

Output: viewer/data.json
Usage:
    python3 src/build_viewer.py
"""
import argparse
import datetime
import difflib
import json
import re
import statistics

import common
import analyze  # reuse _sample_scores / _sd so scoring matches the analysis exactly

VIEWER = (common._EXP / "viewer")
_TOKEN_RE = re.compile(r"\S+|\s+")
RUNS = common.CR_RUNS


def word_spans(a, b):
    """Word-level diff of two strings -> [{op: equal|insert|delete, text}]."""
    at, bt = _TOKEN_RE.findall(a), _TOKEN_RE.findall(b)
    spans = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=at, b=bt, autojunk=False).get_opcodes():
        if tag == "equal":
            spans.append({"op": "equal", "text": "".join(at[i1:i2])})
        elif tag == "delete":
            spans.append({"op": "delete", "text": "".join(at[i1:i2])})
        elif tag == "insert":
            spans.append({"op": "insert", "text": "".join(bt[j1:j2])})
        else:  # replace
            spans.append({"op": "delete", "text": "".join(at[i1:i2])})
            spans.append({"op": "insert", "text": "".join(bt[j1:j2])})
    return [s for s in spans if s["text"]]


def messages_diff(orig, var):
    """Per-message diff spans; fall back to whole-conversation diff if roles/counts diverge."""
    aligned = len(orig) == len(var) and all(
        o.get("role") == v.get("role") for o, v in zip(orig, var))
    if aligned:
        return [{"role": o.get("role", ""), "spans": word_spans(o.get("content", ""), v.get("content", ""))}
                for o, v in zip(orig, var)]
    join = lambda ms: "\n\n".join(f"{m.get('role','')}: {m.get('content','')}" for m in ms)
    return [{"role": "conversation", "spans": word_spans(join(orig), join(var))}]


def _read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def _read_jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _variant(sweep, value):
    for vr in sweep.get("variants", []):
        if vr["value"] == value:
            return vr
    return None


def build_sample(s, ex):
    eid = s["example_id"]
    sweep = _read_json(common.SWEEP / f"{eid}.json")
    if not sweep:
        return None
    variant = _variant(sweep, s["chosen_value"])
    if variant is None:
        return None
    messages_orig = sweep.get("messages_orig", ex["messages"])
    answer_rec = _read_json(common.ANSWERS / f"{eid}.json") or {}
    orig_answers = [a for a in answer_rec.get("orig_answers", []) if a]
    mut_answers = [a for a in answer_rec.get("mut_answers", []) if a]
    grade_rows = {g["idx"]: g for g in _read_jsonl(common.GRADES / f"{eid}.jsonl")}
    pending = not grade_rows

    crit_text = {r["idx"]: r for r in ex["rubrics"]}
    rubrics = []
    for idx in sorted(crit_text):
        r = crit_text[idx]
        g = grade_rows.get(idx)
        row = {"idx": idx, "criterion": r["criterion"], "points": r["points"], "axis": r["axis"]}
        if g:
            row["orig_verdicts"] = [c["verdict"] for c in g.get("orig", [])]
            row["mut_verdicts"] = [c["verdict"] for c in g.get("mut", [])]
            row["orig_expl"] = [c.get("explanation", "") for c in g.get("orig", [])]
            row["mut_expl"] = [c.get("explanation", "") for c in g.get("mut", [])]
        else:
            row["orig_verdicts"] = row["mut_verdicts"] = []
            row["orig_expl"] = row["mut_expl"] = []
        rubrics.append(row)

    # Per-sample scores via the SAME logic the analysis uses.
    scores = None
    sc = analyze._sample_scores(list(grade_rows.values())) if grade_rows else None
    if sc is not None:
        orig_scores, mut_scores, n_crit = sc
        scores = {
            "orig_scores": orig_scores, "mut_scores": mut_scores,
            "orig_mean": statistics.fmean(orig_scores), "mut_mean": statistics.fmean(mut_scores),
            "delta": statistics.fmean(mut_scores) - statistics.fmean(orig_scores),
            "orig_run_sd": analyze._sd(orig_scores), "n_criteria": n_crit,
        }

    return {
        "example_id": eid,
        "dimension": s.get("dimension", sweep.get("dimension", "age")),
        "base_value": sweep.get("base_value"),
        "chosen_value": s["chosen_value"], "chosen_label": s.get("chosen_label", ""),
        "label": f"{s.get('dimension','age')}: base → {s.get('chosen_label','')}",
        "pending": pending,
        "messages_orig": messages_orig,
        "orig_answers": orig_answers, "mut_answers": mut_answers,
        "variant_diff": messages_diff(messages_orig, variant["messages_var"]),
        "change_frac": variant.get("change_frac"), "ok": variant.get("ok", True),
        "rubrics": rubrics,
        "scores": scores,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    args = ap.parse_args()

    selection = common.load_selection()
    by_id = common.examples_by_id([s["example_id"] for s in selection], args.split)

    samples = []
    for s in selection:
        ex = by_id.get(s["example_id"])
        if not ex:
            continue
        sample = build_sample(s, ex)
        if sample:
            samples.append(sample)

    metrics = _read_json(common.RESULTS / "metrics.json")
    dims = sorted({s["dimension"] for s in samples})
    bundle = {
        "meta": {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "version": common._VERSION, "runs": RUNS,
            "judge_temp": common.CM_JUDGE_TEMP, "judge_think": common.CM_JUDGE_THINK,
            "n_items": len(samples), "dimensions": dims,
        },
        "metrics": metrics, "samples": samples,
    }
    VIEWER.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(VIEWER / "data.json", bundle)
    print(f"wrote {len(samples)} samples ({', '.join(dims) or 'none'}) -> {VIEWER/'data.json'}")
    print(f"view with:  python3 -m http.server -d {VIEWER} 8080   then open http://localhost:8080")


if __name__ == "__main__":
    main()
