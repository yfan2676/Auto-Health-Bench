#!/usr/bin/env python3
"""Phase 1 / Step 2a — Heuristic data-dependency scorer (cheap recall filter).

Reads the parsed index and scores every example for how likely it is that
adding *structured patient data* (EHR-style: labs, meds, allergies, conditions,
vitals — i.e. what Synthea can generate) would change the ideal answer and/or
invalidate a rubric criterion. This is a transparent, deterministic first pass;
the LLM classifier (Step 2b) refines the top of this ranking.

Signals
-------
1. Data-field lexicons      -> which structured fields the prompt/rubric reference
   (each field tagged synthea-available vs wearable-only/future).
2. Context-seeking criteria -> a criterion that rewards ASKING for info. If it
   also names a data field, that field is a "moot candidate": supply the data
   and the criterion should disappear / flip.
3. Conditional criteria     -> "if/when/depending on <data>" => the ideal answer
   branches on patient data (induced / urgency-shift candidate).
4. Theme + physician_agreed_category tags HealthBench already provides.

Output (data/derived/, git-ignored — contains HealthBench text):
    candidates.jsonl   every example with score>0, ranked, + matched signals
Console: how many flagged, theme / field distribution.
"""
import json
import re
from collections import Counter
from pathlib import Path

DERIVED = Path("data/derived")

# ---- field lexicons: field -> (regex-pattern-list, synthea_available) ----
FIELD_LEX = {
    "vitals_bp":        (["blood pressure", r"\bbp\b", "systolic", "diastolic", "hypertensive", "hypotens"], True),
    "vitals_hr":        (["heart rate", r"\bpulse\b", "tachycard", "bradycard"], True),
    "vitals_temp":      (["temperature", r"\bfever\b", "febrile"], True),
    "vitals_resp":      (["respiratory rate", "breathing rate"], True),
    "vitals_spo2":      (["oxygen saturation", r"\bspo2\b", "o2 sat", "pulse ox"], True),
    "anthropometry":    (["body mass index", r"\bbmi\b", r"\bweight\b", r"\bheight\b", "obes", "waist circumf"], True),
    "labs_glycemic":    (["hba1c", r"\ba1c\b", "blood glucose", "blood sugar", "fasting glucose", "glucose level"], True),
    "labs_lipids":      (["cholesterol", r"\bldl\b", r"\bhdl\b", "triglyceride", "lipid panel"], True),
    "labs_renal":       (["creatinine", "egfr", r"\bgfr\b", "kidney function", r"\bbun\b"], True),
    "labs_electrolyte": (["potassium", "sodium", "electrolyte", "magnesium"], True),
    "labs_heme":        (["hemoglobin", "hematocrit", r"\bwbc\b", "white blood cell", "platelet", r"\binr\b"], True),
    "labs_thyroid":     ([r"\btsh\b", "thyroid", r"\bt4\b"], True),
    "labs_liver":       ([r"\balt\b", r"\bast\b", "bilirubin", "liver function", r"\blft\b"], True),
    "labs_cardiac":     (["troponin", r"\bbnp\b", "d-dimer"], True),
    "labs_generic":     (["lab result", "lab value", "blood test", "test result", "laboratory", "bloodwork"], True),
    "medications":      (["medication", r"\bmeds\b", r"\bdosage\b", "prescription", "prescribed",
                          "current medication", "taking any", "statin", "metformin", "insulin",
                          "warfarin", "anticoagulant", r"\bssri\b", "antibiotic", r"\bnsaid\b",
                          "ibuprofen", "acetaminophen", "opioid", r"beta.?blocker", "ace inhibitor",
                          "diuretic", "corticosteroid", "chemotherap"], True),
    "allergies":        (["allerg", "intoleran", "anaphylax"], True),
    "conditions_hx":    (["medical history", "past medical history", "history of", "pre-existing",
                          "comorbid", "chronic condition", "problem list", "underlying condition",
                          "diagnosed with", r"\bdiabetes\b", "hypertension", r"\bckd\b",
                          "chronic kidney", r"\bcopd\b", r"\basthma\b", "coronary", r"\bcad\b",
                          "immunocompromis", "pregnan"], True),
    "family_history":   (["family history", "familial"], True),
    "immunizations":    (["vaccin", "immuniz", "flu shot"], True),
    "demographics":     ([r"\bage\b", "how old", "years old", r"\bsex\b", r"\bgender\b"], True),
    # ---- wearable / future (NOT available from Synthea) ----
    "wear_activity":    ([r"\bsteps\b", "step count", "activity level", "physical activity level"], False),
    "wear_sleep":       (["sleep quality", "hours of sleep", "sleep pattern", "sleep duration"], False),
    "wear_hr_trend":    (["resting heart rate", "heart rate variability", r"\bhrv\b", "continuous heart rate"], False),
    "wear_cgm":         (["continuous glucose", r"\bcgm\b", "glucose monitor"], False),
}
FIELD_RE = {f: re.compile("|".join(pats), re.I) for f, (pats, _) in FIELD_LEX.items()}
SYNTHEA_OK = {f for f, (_, ok) in FIELD_LEX.items() if ok}

ASK_RE = re.compile(
    r"\bask(s|ing)?\b|inquir|clarif|more information|additional (information|detail)|"
    r"follow.?up question|gather|elicit|find out|should (ask|inquire|clarify|gather)|"
    r"\brequest(s|ing)?\b.*(info|detail|histor)", re.I)
COND_RE = re.compile(r"\bif (the )?(patient|user|they|client)\b|depending on|"
                     r"\bwhen the (patient|user)\b|in (the )?(case|event)", re.I)

THEME_W = {"context_seeking": 3.0, "health_data_tasks": 3.0, "emergency_referrals": 2.0,
           "hedging": 1.0, "complex_responses": 0.5, "communication": 0.5, "global_health": 0.0}
CAT_W = {"context-matters-but-unclear": 2.0, "context-does-not-matter": -1.5,
         "enough-context": 0.5, "any-reducible-uncertainty": 1.0,
         "enough-info-to-complete-task": 0.5}


def fields_in(text):
    return {f for f, rx in FIELD_RE.items() if rx.search(text)}


def score_example(r):
    prompt = r["prompt_text"]
    prompt_fields = fields_in(prompt)
    moot, conditional, all_crit_fields = [], [], set()
    for i, c in enumerate(r["criteria"]):
        t = c["text"]
        cf = fields_in(t)
        all_crit_fields |= cf
        is_ask = bool(ASK_RE.search(t))
        if is_ask and cf:
            moot.append({"idx": i, "axis": c["axis"], "points": c["points"],
                         "fields": sorted(cf), "text": t})
        if COND_RE.search(t) and cf:
            conditional.append({"idx": i, "axis": c["axis"], "points": c["points"],
                                "fields": sorted(cf), "text": t})

    fields = prompt_fields | all_crit_fields
    synth = sorted(fields & SYNTHEA_OK)
    wear = sorted(fields - SYNTHEA_OK)

    theme_w = sum(THEME_W.get(t, 0) for t in r["themes"])
    cat_w = sum(CAT_W.get(c, 0) for c in r["phys_categories"])
    score = (1.5 * theme_w + cat_w + 1.2 * len(synth) + 0.4 * len(wear)
             + 1.5 * len(moot) + 0.8 * len(conditional) + 0.3 * r["in_hard"])

    return {
        "example_id": r["example_id"],
        "score": round(score, 2),
        "themes": r["themes"],
        "phys_categories": r["phys_categories"],
        "in_hard": r["in_hard"],
        "in_consensus": r["in_consensus"],
        "n_criteria": r["n_criteria"],
        "synthea_fields": synth,
        "wearable_fields": wear,
        "n_moot_candidates": len(moot),
        "n_conditional": len(conditional),
        "moot_candidates": moot,
        "conditional_candidates": conditional,
        "last_user_turn": r["last_user_turn"],
        "prompt_text": r["prompt_text"],
        "criteria": r["criteria"],
    }


def main():
    records = [json.loads(l) for l in (DERIVED / "index.jsonl").open()]
    scored = [score_example(r) for r in records]
    scored.sort(key=lambda x: x["score"], reverse=True)
    cands = [s for s in scored if s["score"] > 0]

    with (DERIVED / "candidates.jsonl").open("w") as f:
        for s in cands:
            f.write(json.dumps(s) + "\n")

    print(f"scored {len(scored)} examples; {len(cands)} with score>0 -> candidates.jsonl")
    print(f"  with >=1 moot candidate (ask-for-data criterion): "
          f"{sum(s['n_moot_candidates']>0 for s in scored)}")
    print(f"  with >=1 synthea-available field:                 "
          f"{sum(len(s['synthea_fields'])>0 for s in scored)}")
    print(f"  with ONLY wearable/future fields:                 "
          f"{sum(len(s['synthea_fields'])==0 and len(s['wearable_fields'])>0 for s in scored)}")

    top = cands[:120]
    th, fld = Counter(), Counter()
    for s in top:
        for t in s["themes"]:
            th[t] += 1
        for fcat in s["synthea_fields"]:
            fld[fcat] += 1
    print("\n  top-120 theme mix:", dict(th.most_common()))
    print("  top-120 field mix:", dict(fld.most_common(12)))
    print("\n  --- top 15 by score ---")
    for s in cands[:15]:
        print(f"  {s['score']:5.1f}  {s['example_id'][:10]}  themes={','.join(s['themes']) or '-':<22} "
              f"moot={s['n_moot_candidates']} cond={s['n_conditional']} "
              f"fields={','.join(s['synthea_fields'][:4])}")


if __name__ == "__main__":
    main()
