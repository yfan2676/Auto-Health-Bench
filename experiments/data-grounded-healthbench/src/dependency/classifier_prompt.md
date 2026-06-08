# Data-dependency classifier — spec (Phase 1 / Step 2b)

Given a HealthBench example (a conversation `prompt` + a physician rubric of
`criteria`), decide whether adding **structured patient data** would change the
ideal answer and/or the rubric, and produce a structured profile.

"Structured patient data" = EHR/record-style fields. Mark each as
`synthea_available` (Synthea can generate it: demographics, conditions/problem
list, medications, allergies, labs, vital signs, encounters, immunizations,
family history) or NOT (high-frequency wearable streams: continuous HR/HRV,
sleep stages, step counts, CGM — these are *future*, not Synthea-able).

## Change types (how the rubric/answer shifts once data is supplied)
- **moot** — a criterion that rewards *asking for* info (e.g. "asks about the
  patient's medications/allergies/history") becomes pointless because the data
  is now in context; the model should *use* it instead, and a model that still
  asks should arguably lose points.
- **induced** — supplying data creates a NEW obligation the original rubric did
  not test (e.g. "correctly notes the documented penicillin allergy contradicts
  the suggested antibiotic").
- **urgency_shift** — the data changes the appropriate level of action/triage
  (e.g. an abnormal lab or vital escalates to an emergency referral).
- **answer_shift** — the substantive recommendation changes (dose, drug choice,
  differential) given the data.

## Be conservative
Only mark `data_dependent: "yes"` when a *specific* structured field would
materially change the ideal response or a criterion. If data merely *could* be
relevant but the generic advice stands, use `"partial"`. If the answer is the
same regardless of record data, use `"no"`.

## Output — write a JSON array, one object per input example, in input order:
```json
{
  "example_id": "<copy EXACTLY from input>",
  "data_dependent": "yes | partial | no",
  "confidence": 0.0-1.0,
  "primary_change_types": ["moot","induced","urgency_shift","answer_shift"],
  "decision_relevant_fields": [
    {"field": "e.g. medications | allergies | HbA1c | systolic_BP | eGFR | resting_HR",
     "synthea_available": true,
     "why": "one clause on why this field changes the answer/rubric"}
  ],
  "affected_existing_criteria": [
    {"excerpt": "<short quote from an existing criterion>",
     "axis": "<its axis>",
     "effect": "becomes_moot | should_reweight | needs_data_grounded_counterpart",
     "explanation": "one sentence"}
  ],
  "proposed_added_criteria": ["<new data-grounded criterion to ADD>", "..."],
  "synthea_patient_spec": {
    "demographics": "age/sex (+ pregnancy if relevant)",
    "conditions": ["..."], "medications": ["..."], "allergies": ["..."],
    "labs": {"name": "value+unit"}, "vitals": {"name": "value+unit"},
    "note": "a concrete, internally-consistent instantiation that makes this example data-dependent"
  },
  "enrichment_summary": "1-2 sentences: how does adding this patient's data change the ideal answer?",
  "wearable_only": false,
  "suitability": "high | medium | low"
}
```
`suitability` = how good a *Phase-1 manual-examination sample* this is: **high**
= clearly data-dependent, Synthea-instantiable, illustrates a clean rubric
change; **low** = weak/ambiguous or needs wearable data we can't generate yet.
