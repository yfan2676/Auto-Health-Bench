#!/usr/bin/env python3
"""Aggregate the LLM-judge results vs the heuristic on the random sample.

Reads data/derived/udeval/{sample_meta.jsonl, judge_*.json} and prints:
  - LLM-judged prevalence (strict / broad) with Wilson 95% CIs  <- the estimate
  - heuristic prevalence on the same sample, and precision/recall vs the LLM
"""
import json
import math
from pathlib import Path

D = Path("data/derived/udeval")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def main():
    meta = {json.loads(l)["idx"]: json.loads(l) for l in (D / "sample_meta.jsonl").open()}
    judge = {}
    for f in sorted(D.glob("judge_*.json")):
        for r in json.loads(f.read_text()):
            judge[r["idx"]] = r
    idxs = [i for i in meta if i in judge]
    n = len(idxs)

    llm_strict = sum(judge[i]["has_structured_data"] for i in idxs)
    llm_broad = sum(judge[i]["has_structured_data"] or judge[i]["dx_history_only"] for i in idxs)
    heur = sum(meta[i]["heuristic_strict"] for i in idxs)

    print(f"sample n = {n}  (missing judgments: {len(meta) - n})\n")
    lo, hi = wilson(llm_strict, n)
    print(f"LLM strict : {llm_strict:3d}/{n} = {100*llm_strict/n:4.1f}%   95% CI [{lo:.1f}, {hi:.1f}]")
    lo, hi = wilson(llm_broad, n)
    print(f"LLM broad  : {llm_broad:3d}/{n} = {100*llm_broad/n:4.1f}%   95% CI [{lo:.1f}, {hi:.1f}]")
    print(f"heuristic  : {heur:3d}/{n} = {100*heur/n:4.1f}%  (full census = 9.1%)\n")

    TP = FP = FN = TN = 0
    for i in idxs:
        h = meta[i]["heuristic_strict"]
        g = judge[i]["has_structured_data"]
        TP += h and g
        FP += h and not g
        FN += (not h) and g
        TN += (not h) and (not g)
    prec = TP / (TP + FP) if TP + FP else 0
    rec = TP / (TP + FN) if TP + FN else 0
    print(f"heuristic vs LLM: TP={TP} FP={FP} FN={FN} TN={TN}")
    print(f"  precision={100*prec:.0f}%  recall={100*rec:.0f}%")

    # category breakdown (LLM)
    from collections import Counter
    cat = Counter()
    for i in idxs:
        for c in judge[i].get("categories", []):
            cat[c] += 1
    print("\nLLM category counts (of YES examples, sample):")
    for k in ("medication", "labs", "vitals", "wearable", "ehr_record"):
        print(f"  {k:12s} {cat[k]:3d}  ({100*cat[k]/n:.1f}% of sample)")


if __name__ == "__main__":
    main()
