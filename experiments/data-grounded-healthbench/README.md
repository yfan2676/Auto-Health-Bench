# Experiment: data-grounded-healthbench

**Goal.** Test the core thesis (see [`../../docs/vision.md`](../../docs/vision.md)):
a HealthBench rubric written for a *text-only* conversation mis-scores model behavior
once the patient's structured data is actually present. This experiment builds the
pipeline that turns HealthBench items into *functions of patient data* and measures the
resulting rubric drift and score shifts.

## Status

- **Phase 1 — rubric mining & data-dependency screening:** done → `reports/phase1-method.md`
- **Phase 2 — data-grounded re-evaluation (proof-of-concept):** done → `reports/phase2-poc.md`
- **Side study — how much user data HealthBench already contains:** done → `reports/user-data-prevalence.md`

## Headline findings

- **~16.8%** of HealthBench conversations (95% CI 14.1–20.0) already contain the
  patient's own structured data; **~0%** contain wearable/sensor data — so ~83% are
  effectively *data-blind*. (`reports/user-data-prevalence.md`)
- **1,791 / 5,000** examples contain ≥1 criterion that rewards *asking for* data a record
  could supply. (`reports/phase1-method.md`)
- On a 30-item data-grounded PoC, the **original** rubric scored a data-*blind* answer
  **59%** but the (correct) data-*aware* answer only **42%** — actively penalizing record
  use in 19/30 items. A **data-conditioned** rubric restored the data-aware answer to
  **71%**. (`reports/phase2-poc.md`)

## Layout

```
data-grounded-healthbench/
├── src/
│   ├── rubrics/      parse.py                       # HealthBench JSONL -> structured index
│   ├── dependency/   score.py, pool.py, select.py   # heuristic scorer -> pool -> shortlist
│   │                 classifier_prompt.md           # LLM data-dependency classifier spec
│   ├── phase2/       build_cases.py, assemble.py,   # instantiate cases, render prompts,
│   │                 make_report.py, make_batches.py#   grade, build the score matrix
│   │                 grading_prompt.md, mutation_prompt.md
│   └── analysis/     user_data_scan.py,             # user-data prevalence (regex census +
│                     build_eval_sample*.py,         #   LLM-judge sample)
│                     eval_aggregate.py
├── data/             HealthBench JSONL + derived/    # git-ignored (see data/README.md)
├── results/          phase1/, phase2/               # small reports committed; bulk ignored
└── reports/          phase1-method.md, phase2-poc.md, user-data-prevalence.md
```

## How to run

All commands run **from this directory** (`experiments/data-grounded-healthbench/`);
the scripts use working-directory-relative paths. First obtain the raw data per
[`data/README.md`](data/README.md), then:

```bash
# --- Phase 1: rubric mining & data-dependency screening ---
python3 src/rubrics/parse.py        # step 1: data/*.jsonl -> data/derived/index.jsonl (+stats)
python3 src/dependency/score.py     # step 2a: heuristic recall filter -> candidates
python3 src/dependency/pool.py      # step 2a: stratified pool + 5 shards
# step 2b: classify the 5 shards with an LLM per src/dependency/classifier_prompt.md
#          -> results/phase1/dep_00..04.json
python3 src/dependency/select.py    # curate -> results/phase1/shortlist.md (+.jsonl)

# --- Phase 2: data-grounded re-evaluation (proof-of-concept) ---
python3 src/phase2/build_cases.py   # instantiate cases + render prompts (3 conditions)
# stage B/C: rubric-mutation + model-under-test + grader subagents (see reports/phase2-poc.md)
#            -> results/phase2/grade_*.json
python3 src/phase2/assemble.py      # score matrix -> results/phase2/{matrix.json, report.md}

# --- Side study: user-data prevalence ---
python3 src/analysis/user_data_scan.py     # regex census over all 5,000 conversations
python3 src/analysis/build_eval_sample.py  # sample for the LLM judge (n=600)
python3 src/analysis/eval_aggregate.py     # aggregate judge results + 95% CI
```

## Data & sharing

`data/` and the **bulk** results (PDF/HTML, per-case `prompt_*`/`resp_*`/`grade_*`/
`rubric_*`, `dep_*`, `cases_all.json`, `shortlist.jsonl`) are git-ignored. The committed
small reports under `results/` and `reports/` include short illustrative HealthBench
snippets — keep the repository private per the dataset's do-not-share notice.
