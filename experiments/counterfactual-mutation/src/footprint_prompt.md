# Footprint-classifier spec (Step 3, dimension = age)

Given a HealthBench conversation and its physician rubric, and a single-dimension edit
(patient age `age_from` → `age_to`), predict — **before any model answer is graded** —
whether each existing criterion's correct verdict changes, and how. This is the
counterfactual-locality *prediction*; `src/sweep_grade.py` + `src/analyze.py` then *test*
it (predicted-`kept` = bridge, should not move; the rest = footprint, should move).

The exact prompt sent to the model is embedded in
[`footprint.py`](footprint.py) (`FOOTPRINT_PROMPT`) so the step is runnable; this file is
the human-readable spec.

## Per-criterion buckets (age-keyed analogue of the data-axis change-types in
`../../data-grounded-healthbench/src/dependency/classifier_prompt.md`)

- **kept** — age-neutral; a good answer satisfies it the same way at both ages. *(bridge)*
- **moot** — rewards asking for / seeking something the new age makes irrelevant.
- **reweight** — still relevant but threshold / strength / expected detail changes with age.
- **urgency** — age changes the appropriate triage / red-flag / referral level.
- **answer_shift** — age changes the substantive recommendation (differential, dose, screening, contraindication).

`age_sensitive = (bucket != "kept")`. Be conservative — default to `kept` unless a
*specific* age-driven clinical reason makes the verdict change.

## Also: proposed induced criteria
New criteria a good answer should now satisfy *because of* the age change (e.g. geriatric
falls/polypharmacy when older; growth/development or guardian involvement when younger).
Not used in the V1/V2 verdict test (they are not in the original rubric), but recorded for
the later mutation step that builds the full R′.

## Output (strict JSON)
```json
{"predictions": [{"idx": <int>, "bucket": "kept|moot|reweight|urgency|answer_shift",
                  "age_sensitive": <bool>, "reason": "<one clause>"}],
 "proposed_induced": ["<new criterion>", "..."]}
```
Every criterion `idx` must appear exactly once; omitted criteria default to `kept`.
