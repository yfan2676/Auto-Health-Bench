#!/usr/bin/env python3
"""Phase 2 / step 1 — Build the proof-of-concept cases.

For each chosen example_id:
  - pull the full conversation + ORIGINAL rubric from data/derived/index.jsonl
  - pull the data-dependency profile (synthea_patient_spec, proposed criteria,
    affected criteria) from results/phase1/shortlist.jsonl
  - render the patient record two ways: a RAW structured dump and a concise
    STRUCTURED SUMMARY (the two context interfaces we test)
  - write rubric-blind prompt files for 3 conditions: baseline / rawdump / summary

NOTE on "Synthea": the patient_spec is a concrete, Synthea-plausible EHR profile
produced in Phase 1. Here we render it directly as a structured record; wiring
the actual Synthea generator (or a keep-module) to emit these exact profiles is
a follow-up — it does not change the evaluation logic below.

Outputs (results/phase2/, git-ignored — contains HealthBench text):
  cases.json
  prompt_<id8>_{baseline,rawdump,summary}.txt
"""
import json
import sys
from pathlib import Path

DERIVED = Path("data/derived")
P1 = Path("results/phase1")
OUT = Path("results/phase2")

# default cases: grapefruit x antihypertensive ; father with pneumonia.
# `build_cases.py all` -> build every entry in the Phase-1 shortlist.
_ALL = sys.argv[1:] == ["all"]
CASE_IDS = None if _ALL else (sys.argv[1:] or [
    "ad5cf7e5-8374-4e12-a03a-1dfcefa2756e",
    "553b75c2-8358-4837-820e-663bc7c16340",
])
OUT_NAME = "cases_all.json" if _ALL else "cases.json"


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).open()]


def render_raw_dump(spec):
    """Verbose, minimally-processed structured EHR export."""
    L = ["=== PATIENT HEALTH RECORD (structured export) ==="]
    L.append(f"Demographics: {spec.get('demographics','(unspecified)')}")

    def section(title, val, bullet=True):
        L.append(f"\n{title}:")
        if not val:
            L.append("  (none on file)")
        elif isinstance(val, dict):
            for k, v in val.items():
                L.append(f"  - {k}: {v}")
        elif isinstance(val, list):
            for v in val:
                L.append(f"  - {v}")
        else:
            L.append(f"  - {val}")

    section("Problem list / Conditions", spec.get("conditions"))
    section("Medications (active)", spec.get("medications"))
    section("Allergies", spec.get("allergies"))
    section("Laboratory results", spec.get("labs"))
    section("Vital signs (most recent)", spec.get("vitals"))
    return "\n".join(L)


def render_summary(spec):
    """Concise clinical précis a system might pre-compute."""
    parts = [spec.get("demographics", "patient")]
    if spec.get("conditions"):
        parts.append("with " + ", ".join(spec["conditions"]))
    if spec.get("medications"):
        parts.append("on " + ", ".join(spec["medications"]))
    if spec.get("allergies"):
        parts.append("allergies: " + ", ".join(spec["allergies"]))
    labs = spec.get("labs") or {}
    if labs:
        parts.append("recent labs " + ", ".join(f"{k} {v}" for k, v in labs.items()))
    vit = spec.get("vitals") or {}
    if vit:
        parts.append("vitals " + ", ".join(f"{k} {v}" for k, v in vit.items()))
    return "PATIENT CONTEXT (summary): " + "; ".join(parts) + "."


def build_prompt(conversation, data_block=None, label=""):
    head = ("You are a health assistant responding to the following message. "
            "Give your best, complete response.\n")
    if data_block:
        head = ("You are a health assistant with access to the relevant "
                "patient's health record (this may be the user themselves, or "
                "the person they are asking about). Use the record where "
                "relevant when responding.\n\n"
                f"{data_block}\n\n")
    return f"{head}\n=== USER MESSAGE ===\n{conversation}\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index = {r["example_id"]: r for r in load_jsonl(DERIVED / "index.jsonl")}
    profiles = {r["example_id"]: r for r in load_jsonl(P1 / "shortlist.jsonl")}
    ids = [r["example_id"] for r in load_jsonl(P1 / "shortlist.jsonl")] if CASE_IDS is None else CASE_IDS

    cases = []
    for eid in ids:
        idx, prof = index[eid], profiles[eid]
        spec = prof.get("synthea_patient_spec", {})
        raw = render_raw_dump(spec)
        summ = render_summary(spec)
        conv = idx["prompt_text"]
        id8 = eid[:8]

        (OUT / f"prompt_{id8}_baseline.txt").write_text(build_prompt(conv))
        (OUT / f"prompt_{id8}_rawdump.txt").write_text(build_prompt(conv, raw))
        (OUT / f"prompt_{id8}_summary.txt").write_text(build_prompt(conv, summ))

        cases.append({
            "example_id": eid, "id8": id8,
            "n_turns": idx["n_turns"],
            "conversation": conv,
            "original_rubric": [
                {"id": i, "criterion": c["text"], "points": c["points"], "axis": c["axis"]}
                for i, c in enumerate(idx["criteria"])
            ],
            "profile": {
                "enrichment_summary": prof.get("enrichment_summary"),
                "primary_change_types": prof.get("primary_change_types"),
                "decision_relevant_fields": prof.get("decision_relevant_fields"),
                "affected_existing_criteria": prof.get("affected_existing_criteria"),
                "proposed_added_criteria": prof.get("proposed_added_criteria"),
            },
            "synthea_patient_spec": spec,
            "patient_raw_dump": raw,
            "patient_summary": summ,
        })

    (OUT / OUT_NAME).write_text(json.dumps(cases, indent=2))
    print(f"built {len(cases)} cases -> {OUT/OUT_NAME}")
    for c in cases:
        print(f"  {c['id8']}  turns={c['n_turns']}  "
              f"orig_criteria={len(c['original_rubric'])}  "
              f"change_types={c['profile']['primary_change_types']}")
        print(f"    prompts: prompt_{c['id8']}_{{baseline,rawdump,summary}}.txt")


if __name__ == "__main__":
    main()
