# Experiment: counterfactual-mutation

**Goal.** Test the **counterfactual-locality hypothesis** (idea doc:
[`../../docs/counterfactual-mutation.md`](../../docs/counterfactual-mutation.md)): if we
edit a *single dimension* of a HealthBench task, can we predict — and *verify* — that the
edit moves only a small, known subset of rubric criteria (the **footprint**), leaving the
rest (the **bridge**) correct verbatim? If so, we can mutate only the footprint and inherit
the rest of the physician rubric, making confident, expert-quality task variants at
edit-distance cost.

This is **E1** of that doc: the cheapest dimension, **patient age** (a pure text edit, no
data synthesis), at small scale — the make-or-break check before scaling or adding harder
dimensions. It reuses the [`../healthbench-local-eval`](../healthbench-local-eval/) LLM
client and the vendored HealthBench grader (no re-implementation of grading).

## Method (the locality test)

Hold one model answer fixed and re-grade it under the original conversation `V` and the
age-edited `V′`. Because the **answer is identical**, any per-criterion verdict change is
caused by the edit. Compared against an a-priori footprint prediction:

- **V1 — bridge invariance:** criteria predicted **kept** should *not* change. The
  **off-target change rate** should sit at the **judge-noise floor** (measured separately).
- **V2 — on-target sensitivity:** criteria predicted in the **footprint** *should* change.

Together → a confusion matrix and **footprint precision/recall**. A clean, local dimension
shows off-target ≈ noise floor and a high on-target rate. The judge runs at **temperature 0**
so the edit is the only varying input.

## Pipeline

```
src/common.py        bridge to healthbench-local-eval (llm client + GRADER_TEMPLATE) + helpers
src/pick.py        Step 1  pick items that state a patient age        -> results/shortlist.jsonl
src/edit.py          Step 2  minimal age edit -> V' (+ diff guard)       -> results/variants/<id>.json
src/footprint.py     Step 3  a-priori per-criterion footprint prediction -> results/footprint/<id>.json
src/answers.py       Step 4  fixed target answer to V (optionally V')    -> results/answers/<id>.json
src/paired_grade.py  Step 5  grade the fixed answer under V and V' (T=0)  -> results/grades/<id>.jsonl
src/noise_floor.py   Step 6  identical-input judge flip rate              -> results/noise_floor.json
src/analyze.py       Step 7  footprint P/R + off-target vs floor          -> results/{metrics.json,report.md}
src/*_prompt.md      human-readable specs for the LLM steps (prompts live in the .py)
```

Each step is resumable (per-item files / appended jsonl, skip-existing) — the same pattern
as the baseline harness.

## How to run

Start the model server once (a single vLLM server serves both the target and the judge —
see [`../healthbench-local-eval/data/README.md`](../healthbench-local-eval/data/README.md)),
then **from this directory**:

```bash
export HB_BACKEND=vllm
export HB_TARGET_BASE_URL=http://localhost:8000/v1  HB_TARGET_MODEL=Qwen/Qwen3-4B
export HB_JUDGE_BASE_URL=http://localhost:8000/v1   HB_JUDGE_MODEL=Qwen/Qwen3-4B
# locality test wants a deterministic judge (default CM_JUDGE_TEMP=0, CM_JUDGE_THINK=0)

python3 src/pick.py       --limit 30     # shortlist 30 age-stating items
python3 src/edit.py                        # make V' for each
python3 src/footprint.py                   # predict the footprint a priori
python3 src/answers.py                     # fixed answer to V  (--also-variant for adaptation test)
python3 src/paired_grade.py                # grade the fixed answer under V and V'
python3 src/noise_floor.py  --k 5 --items 5   # judge-noise floor
python3 src/analyze.py                     # -> results/report.md
```

Config knobs (env): `CM_JUDGE_TEMP` (default 0), `CM_JUDGE_THINK` (0), `CM_AUTHOR_THINK`
(1, for edit/footprint), `CM_DATA_DIR` (override the HealthBench data location). Endpoints
and the target/judge model reuse the `HB_*` vars from the baseline harness.

## Status

- **Scaffold:** complete (this commit). Pipeline runs end-to-end on the baseline vLLM
  harness; no results yet.
- **Note (predicted vs. measured footprint):** `footprint.py` is the *a-priori* (LLM)
  estimator of which criteria the age edit touches. It is only as good as the model — a
  2-item plumbing run with Qwen3-4B predicted *0/22* sensitive, which we cannot trust.
  The stronger, second estimator is **behavioral**: sweep the age over several values and
  see which criteria's verdicts actually move (idea doc §4.1, experiment E1b). `paired_grade.py`
  already grades a fixed answer under one edited variant; the sweep is a loop over K values
  + an invariance aggregation (`sweep.py`, to add). Use the measured footprint as ground
  truth and score the cheap classifier against it.
- **Next:** (1) add `sweep.py` (E1b) for the measured footprint; (2) run E1 at n≈30 (age),
  read `results/report.md` (kill-shot: off-target rate vs. noise floor); consider a stronger
  judge/classifier model on the second GPU; then add D3 (severity) and D2 (mode-of-disclosure)
  per idea doc §5.

## Findings

None yet — to be written into `reports/` after the first run.

## Data & results conventions

`data/` is git-ignored and shared with the baseline harness (see `data/README.md`). Under
`results/`, the small `report.md` / `metrics.json` are committable; bulk per-item files
(`shortlist.jsonl`, `variants/`, `footprint/`, `answers/`, `grades/`) are git-ignored —
they contain HealthBench prompt/rubric text, which must not be shared.
