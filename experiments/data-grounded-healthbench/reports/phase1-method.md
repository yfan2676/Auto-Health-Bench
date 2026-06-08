# Phase 1 — Rubric mining & data-dependency screening (method log)

Implements **steps 1 & 2** of the README §7 pipeline. Goal for this pass is *not*
an exhaustive labeling of HealthBench, but to surface **~30 high-quality,
data-enrichable samples** for manual examination before proceeding.

```
data/*.jsonl ──parse.py──▶ index.jsonl (+stats)
                              │
                       score.py (heuristic recall filter)
                              │  4908 candidates ranked
                       pool.py (stratified sampling)
                              │  72-example pool, 5 shards
              LLM classifier (5 parallel subagents, classifier_prompt.md)
                              │  dep_00..04.json  (72 profiles)
                       select.py (diverse curation)
                              ▼
                 results/phase1/shortlist.md  ← the 30 samples to examine
```

All scripts are deterministic except the LLM classifier. Re-run end-to-end:

```bash
python3 src/rubrics/parse.py        # step 1
python3 src/dependency/score.py     # step 2a — heuristic scorer
python3 src/dependency/pool.py      # step 2a — stratified pool + shards
# step 2b — run the 5 shards through an LLM per src/dependency/classifier_prompt.md
python3 src/dependency/select.py    # curate the shortlist
```

## Step 1 — Rubric mining (`src/rubrics/parse.py`)
Flattens `healthbench_full.jsonl` (5000 examples; hard/consensus add membership
flags) into `data/derived/index.jsonl`, one structured record per example
(conversation, themes, physician categories, criteria with axis/points/tags).

**Corpus stats (full set):**
- 5,000 examples; 1,000 also in Hard, 3,671 in Consensus.
- 57,237 rubric criteria total (mean 11.5/example, range 2–48).
- 2,085 examples are multi-turn (up to 19 turns).
- Points sign: 39,662 positive (rewards) vs **17,575 negative (penalties)**.
- Axis mix: completeness 38.9%, accuracy 33.0%, context-awareness 15.7%,
  communication 7.9%, instruction-following 4.5%.
- Themes: global_health 1097, hedging 1071, communication 919,
  **context_seeking 594, emergency_referrals 482, health_data_tasks 477**,
  complex_responses 360.

## Step 2a — Heuristic data-dependency scorer (`score.py`, `pool.py`)
A transparent, deterministic recall filter (no model). Per example it detects:
1. **Data-field lexicons** (regex) → which structured fields the prompt/rubric
   reference, tagged Synthea-available vs wearable-only/future.
2. **Moot candidates** — a criterion that rewards *asking for* a data field
   (e.g. "asks about the patient's medications"); supplying the data should make
   it moot.
3. **Conditional criteria** — "if/when/depending on <data>" → answer branches on
   patient data.
4. HealthBench's own **theme** and **physician_agreed_category** tags (weighted).

`score = 1.5·Σtheme_w + Σcat_w + 1.2·#synthea_fields + 0.4·#wearable_fields
         + 1.5·#moot + 0.8·#conditional + 0.3·in_hard`

**Result:** 4,908/5,000 score >0; **1,791** have ≥1 ask-for-data ("moot")
criterion; 4,361 reference ≥1 Synthea-able field; 303 reference *only*
wearable/future fields.

Because a raw top-N is dominated by context-seeking "ask for history" cases,
`pool.py` instead pulls the top of each **stratum** and de-dups:

| Stratum | meaning | available | quota |
|---|---|---|---|
| A | context-seek + ≥3 ask-for-data criteria (moot) | 206 | 14 |
| B | health_data_tasks (interpret data) | 477 | 14 |
| C | emergency_referrals (urgency may flip) | 482 | 14 |
| D | names specific labs (glycemic/renal/lipid/cardiac…) | 1173 | 14 |
| E | numeric vitals (BP/SpO₂/HR) + conditional/hard | 290 | 10 |
| F | wearable-keyed (flagged: NOT Synthea-able) | 2884 | 6 |

→ **72-example pool**, sharded ×5 for parallel classification.

## Step 2b — LLM data-dependency classifier (`classifier_prompt.md`)
Five parallel subagents classify the shards against a strict schema, judging
strictly from the supplied prompt + rubric. Each profile records: data_dependent
(yes/partial/no) + confidence; change types (**moot / induced / urgency_shift /
answer_shift**); decision-relevant fields (+Synthea-availability); which existing
criteria break and how; proposed data-grounded criteria to ADD; a concrete
Synthea patient spec; and a suitability rating.

**Result over the 72-example pool:** 46 `yes`, 22 `partial`, 4 `no`; 44 rated
high-suitability.

> Validation here is the LLM classifier itself (a *proxy*, per the README's
> "physician access: not now" decision). Physician calibration is a later
> milestone; these labels are pre-validation.

## Curation — the 30 samples (`select.py`)
From the 46 `yes` profiles, a greedy diverse selection balances across strata
and caps wearable-only examples, producing **30 high-suitability samples** in
`results/phase1/shortlist.md` (+ `.jsonl`).

- Primary-stratum fill: B 6, C 6, E 4, D 6, A 3 (+top-up to 30).
- Change-type coverage: induced 29, moot 28, answer_shift 25, urgency_shift 6.
- **0 wearable-only** survived to the final set — consistent with the
  Synthea-first decision; the drivers are EHR-style fields (medications,
  conditions, allergies, labs, vitals). Wearable-keyed examples remain in the
  pool (stratum F) if the wearable angle is pursued later.

**Illustrative samples** (why the thesis holds):
- *Grapefruit × antihypertensive* — "asks which BP medication" becomes moot once
  the med list is in context; a documented dihydropyridine CCB (felodipine)
  would *flip* the answer (answer_shift on a single field).
- *"Cholestérol élevé"* — supplying LDL 191 / low HDL + family history converts
  "ask for your lipid values" into "interpret these values and escalate therapy."
- *Father with pneumonia* — a documented penicillin allergy makes the rubric's
  first-line amoxicillin-clavulanate unsafe (induced obligation → regimen change).

## Outputs & sharing
Scripts, the classifier spec, and this log are committed. Everything containing
HealthBench text is **git-ignored** (`data/derived/`, `results/`) per the
dataset's do-not-share notice — examine `results/phase1/shortlist.md` locally.

## Limitations / notes
- The heuristic scorer optimizes **recall**, not precision; the LLM pass and
  curation supply precision.
- Classifier labels are **proxy** (LLM, single pass) — not physician-validated.
- Synthea cannot produce high-frequency sensor streams; wearable-dependent cases
  are deferred.
- Curation favors **diversity** over raw score, so the 30 are illustrative of the
  range, not the 30 highest-scoring examples.

## Next (Phase 2)
Instantiate the `synthea_patient_spec` for several of these samples, build the
augmented prompt under both interfaces (raw dump / structured summary), run a
model, and place the original vs. mutated rubric side-by-side to document the gap.
