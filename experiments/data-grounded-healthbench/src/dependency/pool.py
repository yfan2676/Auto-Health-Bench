#!/usr/bin/env python3
"""Phase 1 / Step 2a (cont.) — Build a STRATIFIED candidate pool for the LLM pass.

Taking the global top-by-score over-represents context-seeking "ask for medical
history" examples. For a diverse set the user can manually examine, we instead
pull the top-scoring examples within each of several strata that matter for the
data-conditioning thesis, then de-dup.

Strata:
    A context_seek_moot  context_seeking theme + >=3 ask-for-data criteria   (moot-type)
    B health_data_tasks  must interpret supplied data                        (answer-shift)
    C emergency_referral urgency may flip on data                            (urgency)
    D numeric_labs       names specific labs (glycemic/renal/lipid/cardiac…) (numeracy)
    E numeric_vitals     BP/SpO2/HR, esp. with a conditional criterion       (numeracy/urgency)
    F wearable_future    keyed on wearable data (flagged: NOT Synthea-able)

Outputs (data/derived/, git-ignored):
    pool.jsonl                  the merged, de-duped pool (with a "strata" tag)
    pool_00..NN.jsonl           shards for parallel LLM classification
"""
import json
import math
from pathlib import Path

DERIVED = Path("data/derived")
N_SHARDS = 5
LAB_FIELDS = {"labs_glycemic", "labs_renal", "labs_lipids", "labs_cardiac",
              "labs_heme", "labs_thyroid", "labs_liver", "labs_generic"}
NUM_VITALS = {"vitals_bp", "vitals_spo2", "vitals_hr"}

QUOTAS = {"A": 14, "B": 14, "C": 14, "D": 14, "E": 10, "F": 6}


def in_stratum(s):
    out = []
    th = set(s["themes"])
    sf = set(s["synthea_fields"])
    if "context_seeking" in th and s["n_moot_candidates"] >= 3:
        out.append("A")
    if "health_data_tasks" in th:
        out.append("B")
    if "emergency_referrals" in th:
        out.append("C")
    if sf & LAB_FIELDS:
        out.append("D")
    if (sf & NUM_VITALS) and (s["n_conditional"] >= 1 or s["in_hard"]):
        out.append("E")
    if s["wearable_fields"]:
        out.append("F")
    return out


def main():
    cands = [json.loads(l) for l in (DERIVED / "candidates.jsonl").open()]
    # candidates.jsonl is already sorted by score desc
    by_stratum = {k: [] for k in QUOTAS}
    for s in cands:
        for st in in_stratum(s):
            by_stratum[st].append(s)

    print("stratum availability (>0 score):")
    for k in QUOTAS:
        print(f"  {k}: {len(by_stratum[k]):4d} available, taking up to {QUOTAS[k]}")

    pool, seen = [], set()
    for k, q in QUOTAS.items():
        taken = 0
        for s in by_stratum[k]:
            if taken >= q:
                break
            if s["example_id"] in seen:
                # already pulled by another stratum; just record the extra tag
                for p in pool:
                    if p["example_id"] == s["example_id"] and k not in p["strata"]:
                        p["strata"].append(k)
                continue
            rec = dict(s)
            rec["strata"] = [k]
            pool.append(rec)
            seen.add(s["example_id"])
            taken += 1

    with (DERIVED / "pool.jsonl").open("w") as f:
        for p in pool:
            f.write(json.dumps(p) + "\n")

    # shard for parallel classification
    shard_sz = math.ceil(len(pool) / N_SHARDS)
    for i in range(N_SHARDS):
        chunk = pool[i * shard_sz:(i + 1) * shard_sz]
        if not chunk:
            continue
        with (DERIVED / f"pool_{i:02d}.jsonl").open("w") as f:
            for p in chunk:
                f.write(json.dumps(p) + "\n")

    print(f"\npool size = {len(pool)} unique examples -> pool.jsonl + {N_SHARDS} shards")
    from collections import Counter
    sc = Counter()
    for p in pool:
        for st in p["strata"]:
            sc[st] += 1
    print("pool strata coverage (with overlaps):", dict(sorted(sc.items())))


if __name__ == "__main__":
    main()
