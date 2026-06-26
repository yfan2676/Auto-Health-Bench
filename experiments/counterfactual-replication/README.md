# Counterfactual replication: does a mutation move the score?

This experiment asks a single question: when you mutate one dimension of a HealthBench task
(patient age, mode of disclosure, severity, pregnancy status, an added comorbidity, or sex),
does the model's overall rubric score change in a way that is statistically real, above the
model's own run-to-run noise?

It is the significance-test sibling of `../counterfactual-mutation`. That experiment studies
which individual rubric criteria flip (the "footprint"), with a single answer/grade pass and a
deterministic judge. This one drops the footprint entirely, replicates each answer-and-grade 3
times so noise can be measured, and runs a paired significance test on the overall score.

## Design

- **Model:** `Qwen/Qwen3.6-27B-FP8` for BOTH the answerer and the judge, thinking enabled, at
  Qwen3's recommended thinking-mode sampling (temperature 0.6, top_p 0.95, top_k 20, min_p 0).
  The judge is not held constant here: replication captures its sampling noise too.
- **Samples:** 25 drawn at random per dimension (6 dimensions), 150 total.
- **One mutation per sample:** age and disclosure carry 3 candidate variants; one is chosen at
  random per sample. The other dimensions already have a single variant. The mutated inputs are
  reused verbatim from `../counterfactual-mutation/results/sweep/` (they are model-independent
  text edits), so nothing is re-generated.
- **Replication:** 3 independent answers to the original input and 3 to the chosen mutation, per
  sample. Each answer is graded against the SAME original rubric (the controlled comparison:
  only the input changes). Every response and grade is kept.
- **Hardware:** one vLLM replica per GPU on 4x H200. All answers are generated first, then all
  grading runs, each fanned across the 4 GPUs.

## What it reports (per dimension, and pooled)

- Change in the overall score (mutated minus original), absolute and signed, plus whether each
  of the 3 paired runs went up or down.
- The standard deviation of the 3 original-run overall scores: the run-to-run noise floor with
  no input change.
- A significance verdict. The primary test is a **paired test across the 25 samples** (each
  sample's score is the mean over its 3 runs); the paired t-test p-value is the headline, with a
  sign-flip permutation test and a Wilcoxon signed-rank test as robustness checks. Cohen's d_z is
  reported as the effect size. All statistics are pure-Python (`src/stats.py`), no numpy/scipy.

## How to run

```bash
cd experiments/counterfactual-replication
./run_replication.sh                       # full run: 150 samples, 3 runs, 4 GPUs
CR_RUNS=1 CR_PER_DIM=2 CR_VERSION=smoke ./run_replication.sh   # quick end-to-end smoke test
```

The driver serves the four 27B servers, runs the pipeline, and always tears the servers down on
exit. Every step is resumable (skip-existing), so a re-run continues where it stopped.

Step by step (servers must already be up; see `run_replication.sh` for the serve commands):

```bash
python3 src/sample.py          # pick 25/dim + one variant each   -> results/selection.jsonl
python3 src/answers.py         # 3 orig + 3 mut answers per sample -> results/answers_<ver>/
python3 src/grade.py           # grade all answers vs orig rubric  -> results/grades_<ver>/
python3 src/analyze.py         # significance + score change       -> results/metrics.json, report.md
python3 src/build_viewer.py    # static viewer bundle              -> viewer/data.json
python3 -m http.server -d viewer 8080   # open http://localhost:8080
```

Key knobs (env): `CR_RUNS` (replicates, default 3), `CR_PER_DIM` (samples per dimension, default
25), `CR_SEED` (selection + permutation seed), `CR_VERSION` (results subdir tag), `CR_PERM`
(permutation resamples). Model/endpoint/sampling come from the same `HB_*` / `CM_*` env vars as
the sibling harness (see `src/common.py`).

## Layout

```
run_replication.sh        4-GPU driver: serve -> sample -> answers -> grade -> analyze -> viewer
src/sample.py             deterministic 25/dim + one-variant selection
src/answers.py            3 original + 3 mutated answers per sample (one batched fan-out)
src/grade.py              grade every answer vs the original rubric (orig x3 + mut x3)
src/analyze.py            per-sample scores, per-dimension change, paired significance tests
src/stats.py              pure-Python paired t-test, sign-flip permutation, Wilcoxon
src/build_viewer.py       aggregate into viewer/data.json
src/common.py             bridge to ../healthbench-local-eval (LLM client + grader), paths, pmap
viewer/index.html         static viewer: inputs, the mutated diff, all answers, verdict grid
results/shortlist.jsonl   detected item set (copied from counterfactual-mutation)
results/sweep/            mutated inputs (copied; model-independent text edits)
results/selection.jsonl   the 150 chosen samples
results/answers_<ver>/    fresh answers (3 orig + 3 mut per sample)
results/grades_<ver>/     per-criterion verdicts (orig x3 + mut x3)
results/metrics.json      per-dimension significance + per-sample scores
results/report.md         human-readable summary tables
```

The shared HealthBench split lives at `data/healthbench_full.jsonl` (a symlink to the sibling's
copy; `CM_DATA_DIR` is a fallback). It is git-ignored.
