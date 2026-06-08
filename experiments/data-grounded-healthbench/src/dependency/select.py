#!/usr/bin/env python3
"""Phase 1 / Step 2b (cont.) — Aggregate classifier output and curate ~30 samples.

Merges the LLM classifier profiles (results/phase1/dep_*.json) with the pool
metadata (data/derived/pool.jsonl), then selects a diverse ~30-example shortlist
for manual examination, balancing across strata and capping wearable-only
(non-Synthea) examples.

Outputs (results/phase1/, git-ignored — contains HealthBench text):
    shortlist.jsonl   machine-readable merged records for the selected samples
    shortlist.md      human-readable report (what the user examines)
"""
import json
import textwrap
from pathlib import Path

DERIVED = Path("data/derived")
OUT = Path("results/phase1")

SUIT_RANK = {"high": 0, "medium": 1, "low": 2}
# single primary stratum per example, by priority (rarer / more interesting first)
PRIORITY = ["B", "C", "E", "D", "A"]
QUOTA = {"B": 6, "C": 6, "E": 4, "D": 6, "A": 4}   # = 26 synthea + 4 wearable = 30
N_WEARABLE = 4


def primary_stratum(strata):
    for s in PRIORITY:
        if s in strata:
            return s
    return strata[0] if strata else "A"


def load():
    pool = {json.loads(l)["example_id"]: json.loads(l)
            for l in (DERIVED / "pool.jsonl").open()}
    profs = {}
    for f in sorted(OUT.glob("dep_*.json")):
        for p in json.loads(f.read_text()):
            profs[p["example_id"]] = p
    merged = []
    for eid, prof in profs.items():
        meta = pool.get(eid, {})
        merged.append({**prof, "_strata": meta.get("strata", []),
                       "_themes": meta.get("themes", []),
                       "_in_hard": meta.get("in_hard", False),
                       "_score": meta.get("score"),
                       "_last_user_turn": meta.get("last_user_turn", ""),
                       "_criteria": meta.get("criteria", [])})
    return merged


def sort_key(r):
    return (SUIT_RANK.get(r.get("suitability"), 3), -float(r.get("confidence", 0)),
            -(r.get("_score") or 0))


def select(merged):
    yes = [r for r in merged if r.get("data_dependent") == "yes"]
    yes.sort(key=sort_key)

    chosen, used = [], set()

    # 1) wearable-only (future) — capped, flagged
    wear = [r for r in yes if r.get("wearable_only")]
    for r in wear[:N_WEARABLE]:
        chosen.append(r); used.add(r["example_id"])

    # 2) synthea-able, balanced across strata by primary assignment
    counts = {k: 0 for k in QUOTA}
    synth = [r for r in yes if not r.get("wearable_only") and r["example_id"] not in used]
    for r in synth:
        ps = primary_stratum(r["_strata"])
        if ps in counts and counts[ps] < QUOTA[ps]:
            chosen.append(r); used.add(r["example_id"]); counts[ps] += 1

    # 3) top up to 30 with best remaining synthea-able
    for r in synth:
        if len(chosen) >= 30:
            break
        if r["example_id"] not in used:
            chosen.append(r); used.add(r["example_id"])

    chosen.sort(key=sort_key)
    return chosen, counts


def md_sample(i, r):
    fields = "; ".join(f"`{f['field']}`{'' if f.get('synthea_available') else ' (wearable/future)'}"
                       f" — {f.get('why','')}" for f in r.get("decision_relevant_fields", []))
    aff = "\n".join(f"  - _{c.get('effect')}_: \"{c.get('excerpt','')[:160]}\" — {c.get('explanation','')}"
                    for c in r.get("affected_existing_criteria", []))
    added = "\n".join(f"  - {c}" for c in r.get("proposed_added_criteria", []))
    spec = r.get("synthea_patient_spec", {})
    spec_lines = "\n".join(f"  - **{k}:** {json.dumps(v) if isinstance(v,(dict,list)) else v}"
                           for k, v in spec.items())
    wb = " **[WEARABLE/FUTURE — not Synthea-able]**" if r.get("wearable_only") else ""
    return f"""### {i}. `{r['example_id']}`{wb}
- **strata:** {', '.join(r['_strata'])} | **themes:** {', '.join(r['_themes']) or '—'} | **hard:** {r['_in_hard']}
- **data_dependent:** {r.get('data_dependent')} | **confidence:** {r.get('confidence')} | **suitability:** {r.get('suitability')}
- **change types:** {', '.join(r.get('primary_change_types', []))}
- **enrichment:** {r.get('enrichment_summary','')}
- **decision-relevant fields:** {fields}
- **affected existing criteria:**
{aff or '  - (none)'}
- **proposed added (data-grounded) criteria:**
{added or '  - (none)'}
- **example Synthea patient spec:**
{spec_lines or '  - (none)'}
- **original user turn (excerpt):** {textwrap.shorten(r.get('_last_user_turn','').replace(chr(10),' '), 280)}
"""


def main():
    merged = load()
    chosen, counts = select(merged)

    with (OUT / "shortlist.jsonl").open("w") as f:
        for r in chosen:
            f.write(json.dumps(r) + "\n")

    # summary tallies
    from collections import Counter
    ct, fld = Counter(), Counter()
    nwear = 0
    for r in chosen:
        for c in r.get("primary_change_types", []):
            ct[c] += 1
        for fc in r.get("decision_relevant_fields", []):
            fld[fc["field"]] += 1
        nwear += bool(r.get("wearable_only"))

    header = f"""# Phase 1 shortlist — {len(chosen)} data-enrichable HealthBench samples

Curated for manual examination. Generated by `src/rubrics/parse.py` →
`src/dependency/{{score,pool,select}}.py` + an LLM classifier
(`classifier_prompt.md`). **Contains HealthBench text — do not share.**

- **Selection:** from a 72-example stratified pool (46 classified `data_dependent=yes`),
  balanced across strata; wearable-only examples capped at {nwear} and flagged.
- **Primary-stratum fill:** {dict(counts)} (+{nwear} wearable)
- **Change-type coverage:** {dict(ct)}
- **Most-cited fields:** {dict(fld.most_common(12))}

Strata legend: A=context-seek/moot, B=health-data-tasks, C=emergency-referrals,
D=numeric-labs, E=numeric-vitals, F/wearable=future.

Look up full prompt + rubric for any `example_id` in `data/derived/index.jsonl`.

---

"""
    body = "\n".join(md_sample(i + 1, r) for i, r in enumerate(chosen))
    (OUT / "shortlist.md").write_text(header + body)

    print(f"selected {len(chosen)} samples -> {OUT/'shortlist.md'} + shortlist.jsonl")
    print("  primary-stratum fill:", dict(counts), f"(+{nwear} wearable)")
    print("  change types:", dict(ct))
    print("  suitability:", dict(Counter(r.get("suitability") for r in chosen)))


if __name__ == "__main__":
    main()
