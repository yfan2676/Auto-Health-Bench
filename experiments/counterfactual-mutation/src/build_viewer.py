#!/usr/bin/env python3
"""Build the static viewer's data bundle: aggregate every per-item result file into one
self-contained viewer/data.json that viewer/index.html renders. No model calls; rerun any
time the results change.

For each tested sample it joins: the shortlist (dimension, base value), the K-value sweep
(src/sweep.py — original + edited conversations), the a-priori footprint prediction
(src/footprint.py), the model's fresh answer to each input (src/answers.py), and the measured
per-criterion sweep verdicts (src/sweep_grade.py). Diff-highlight spans between the original and each edited
conversation are precomputed here with difflib (word granularity) so the HTML stays
dependency-free — it just paints spans tagged equal/insert/delete.

Privacy: viewer/data.json embeds verbatim HealthBench prompt/rubric/judge text for the tested
subset only. Committing a small subset is allowed under the repo-wide policy (only the full
original dataset must stay out), so THIS experiment's bundle IS committed (negation in root
.gitignore) to render on a fresh clone. viewer/index.html and this script are code and sync.

Output: viewer/data.json
Usage:
    python3 src/build_viewer.py
    python3 src/build_viewer.py --split full
"""
import argparse
import datetime
import difflib
import json
import re
from pathlib import Path

import common

VIEWER = (common._EXP / "viewer")
_TOKEN_RE = re.compile(r"\S+|\s+")


def _confusion(predicted_sensitive, changed):
    # Standard orientation: predicted-sensitive -> TP if it moved else FP (false alarm);
    # predicted-kept -> FN if it moved (off-target / bridge leak) else TN.
    return ("TP" if changed else "FP") if predicted_sensitive else ("FN" if changed else "TN")


def word_spans(a, b):
    """Word-level diff of two strings -> [{op: equal|insert|delete, text}]. A 'replace'
    becomes a delete span (old) followed by an insert span (new)."""
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
    """Per-message diff spans. If message counts/roles diverge (e.g. a D2 turn rewrite),
    fall back to diffing the whole conversation as one block."""
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


def build_sample(s, ex):
    eid = s["example_id"]
    sweep = _read_json(common.SWEEP / f"{eid}.json")
    if not sweep:
        return None  # nothing to show without the edited conversations
    footprint = _read_json(common.FOOTPRINT / f"{eid}.json") or {}
    answer_rec = _read_json(common.ANSWERS / f"{eid}.json") or {}
    grade_rows = {g["idx"]: g for g in _read_jsonl(common.SWEEP_GRADES / f"{eid}.jsonl")}
    preds = {p["idx"]: p for p in footprint.get("predictions", [])}

    messages_orig = sweep.get("messages_orig", ex["messages"])
    answer = answer_rec.get("answer", "")
    var_answer = {va["value"]: va["answer"] for va in answer_rec.get("variant_answers", [])}

    # Variants (edited inputs) with precomputed diff spans + the model's fresh answer to each.
    variants = [{
        "value": vr["value"], "label": vr["label"],
        "messages_diff": messages_diff(messages_orig, vr["messages_var"]),
        "change_frac": vr.get("change_frac"), "ok": vr.get("ok", True),
        "fact_preserved": vr.get("extra", {}).get("fact_preserved"),
        "data_phrase": vr.get("extra", {}).get("data_phrase"),
        "answer": var_answer.get(vr["value"], ""),
    } for vr in sweep.get("variants", [])]

    # Unified rubric list: criterion text + a-priori prediction + measured sweep verdicts.
    rubrics = []
    tp = fp = fn = tn = 0
    for r in ex["rubrics"]:
        idx = r["idx"]
        p = preds.get(idx, {})
        bucket = p.get("bucket", "kept")
        predicted_sensitive = bool(p.get("predicted_sensitive", p.get("age_sensitive", bucket != "kept")))
        g = grade_rows.get(idx)
        if g:
            changed = bool(g.get("changed"))
            conf = _confusion(predicted_sensitive, changed)
            tp += conf == "TP"; fp += conf == "FP"; fn += conf == "FN"; tn += conf == "TN"
            rubrics.append({
                "idx": idx, "criterion": r["criterion"], "points": r["points"], "axis": r["axis"],
                "predicted_bucket": bucket, "predicted_sensitive": predicted_sensitive,
                "predicted_reason": p.get("reason", ""),
                "verdict_orig": g.get("verdict_orig"), "explanation_orig": g.get("explanation_orig", ""),
                "sweep": g.get("sweep", []),
                "changed": changed, "flip_values": g.get("flip_values", []), "confusion": conf,
            })
        else:  # not graded yet — still show criterion + prediction
            rubrics.append({
                "idx": idx, "criterion": r["criterion"], "points": r["points"], "axis": r["axis"],
                "predicted_bucket": bucket, "predicted_sensitive": predicted_sensitive,
                "predicted_reason": p.get("reason", ""),
                "verdict_orig": None, "explanation_orig": "", "sweep": [],
                "changed": None, "flip_values": [], "confusion": None,
            })

    def safe(a, b):
        return (a / b) if b else None

    return {
        "example_id": eid, "dimension": sweep.get("dimension", s.get("dimension", "age")),
        "base_value": sweep.get("base_value"), "values": sweep.get("values", []),
        "label": f"{sweep.get('dimension','age')} {sweep.get('base_value')} → {sweep.get('values', [])}",
        "messages_orig": messages_orig, "answer": answer,
        "proposed_induced": footprint.get("proposed_induced", []),
        "rubrics": rubrics, "variants": variants,
        "sample_metrics": {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": safe(tp, tp + fp), "recall": safe(tp, tp + fn),
            "off_target_rate": safe(fn, fn + tn),  # bridge (predicted-kept) criteria that moved
            "n_criteria": tp + fp + fn + tn,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    by_id = common.examples_by_id([s["example_id"] for s in shortlist], args.split)

    samples = []
    for s in shortlist:
        ex = by_id.get(s["example_id"])
        if not ex:
            continue
        sample = build_sample(s, ex)
        if sample:
            samples.append(sample)

    metrics = _read_json(common.RESULTS / "metrics.json")
    noise_floor = _read_json(common.NOISE_FLOOR)
    dims = sorted({s["dimension"] for s in samples})

    bundle = {
        "meta": {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "judge_temp": common.CM_JUDGE_TEMP, "judge_think": common.CM_JUDGE_THINK,
            "n_items": len(samples), "dimensions": dims,
        },
        "metrics": metrics, "noise_floor": noise_floor, "samples": samples,
    }
    VIEWER.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(VIEWER / "data.json", bundle)
    print(f"wrote {len(samples)} samples ({', '.join(dims) or 'none'}) -> {VIEWER/'data.json'}")
    print(f"view with:  python3 -m http.server -d {VIEWER} 8080   then open http://localhost:8080")


if __name__ == "__main__":
    main()
