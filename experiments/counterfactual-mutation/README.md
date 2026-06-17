# Experiment: counterfactual-mutation

> **New here?** Read [`OVERVIEW.md`](OVERVIEW.md) first — a 2-3 min explainer of the idea,
> the pipeline diagram, and the data flow.

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

The **sweep** path (recommended — E1b, the *measured* footprint over K~3 values) and an
interactive **viewer**:

```
src/common.py        bridge to healthbench-local-eval (llm client + GRADER_TEMPLATE) +
                     pmap (multi-GPU grading), diff helpers
src/pick.py        Step 1  pick items that state a patient age        -> results/shortlist.jsonl
src/sweep.py         Step 2  K~3-value sweep of minimal edits (+guard)   -> results/sweep/<id>.json
src/footprint.py     Step 3  a-priori per-criterion footprint prediction -> results/footprint/<id>.json
src/answers.py       Step 4  fixed target answer to V                    -> results/answers/<id>.json
src/sweep_grade.py   Step 5  grade fixed answer under V + each value (T=0, concurrent across GPUs)
                                                                         -> results/sweep_grades/<id>.jsonl
src/noise_floor.py   Step 6  identical-input judge flip rate              -> results/noise_floor.json
src/analyze.py       Step 7  footprint P/R + off-target vs floor (+by-dim) -> results/{metrics.json,report.md}
src/build_viewer.py  Step 8  aggregate everything (+difflib spans)        -> viewer/data.json
viewer/index.html    dependency-free static viewer (serve with python -m http.server)
```

A criterion is in the **measured footprint** iff its verdict (of the *fixed* answer) flips
vs. the original at *any* swept value; invariant across the whole sweep ⇒ bridge. `analyze.py`
scores the a-priori footprint classifier against this behavioral truth (precision/recall,
off-target vs. noise floor), broken down by dimension and rubric axis. Each step is resumable
(per-item files / appended jsonl, skip-existing).

> The original single-edit path (`src/edit.py` Step 2 → `results/variants/`,
> `src/paired_grade.py` Step 5 → `results/grades/`) is kept for V1/V2 on one A→B edit;
> `analyze.py` reads `sweep_grades/` if present, else falls back to `grades/`.

## How to run

Start **two** vLLM servers (one per GPU — grading fans across both) — see
[`../healthbench-local-eval/data/README.md`](../healthbench-local-eval/data/README.md):

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-4B --port 8000 --gpu-memory-utilization 0.85 --max-model-len 32768 &
CUDA_VISIBLE_DEVICES=1 vllm serve Qwen/Qwen3-4B --port 8001 --gpu-memory-utilization 0.85 --max-model-len 32768 &
```

Then **from this directory**:

```bash
export HB_BACKEND=vllm
export HB_TARGET_BASE_URL=http://localhost:8000/v1  HB_TARGET_MODEL=Qwen/Qwen3-4B
export HB_JUDGE_BASE_URLS=http://localhost:8000/v1,http://localhost:8001/v1  HB_JUDGE_MODEL=Qwen/Qwen3-4B
export HB_THINK_JUDGE=0   # non-thinking judge ≈ 10x faster grading
# locality test wants a deterministic judge (default CM_JUDGE_TEMP=0, CM_JUDGE_THINK=0)

python3 src/pick.py        --limit 30   # shortlist 30 age-stating items
python3 src/sweep.py                     # K~3-value sweep per item
python3 src/footprint.py                 # predict the footprint a priori
python3 src/answers.py                   # fixed answer to V
python3 src/sweep_grade.py               # grade the fixed answer under V + each swept value
python3 src/noise_floor.py  --k 5 --items 5   # judge-noise floor
python3 src/analyze.py                   # -> results/report.md (off-target vs floor, by dimension)
python3 src/build_viewer.py              # -> viewer/data.json
python3 -m http.server -d viewer 8080    # open http://localhost:8080
```

**D2 (mode of disclosure)** runs on the same machinery — just pick it (it *appends* to the
shortlist, keeping the D1 rows), then run the shared steps once for both dimensions:

```bash
python3 src/pick.py --dimension disclosure --limit 30   # re-encodable stated facts (regex + LLM confirm)
python3 src/sweep.py && python3 src/footprint.py && python3 src/answers.py && python3 src/sweep_grade.py
python3 src/analyze.py && python3 src/build_viewer.py    # one report + viewer covering D1 and D2
```

Config knobs (env): `HB_JUDGE_BASE_URLS` (comma-separated judge URLs, one per GPU),
`CM_JUDGE_CONCURRENCY` (grading threads per endpoint, default 8), `HB_MAX_TOKENS`
(**set 16384** — the a-priori footprint author call with thinking on can exceed 8192 on items
with many rubrics), `CM_JUDGE_TEMP` (default 0), `CM_JUDGE_THINK` (0), `CM_AUTHOR_THINK` (1),
`CM_DATA_DIR`. Endpoints and the target/judge model reuse the `HB_*` vars from the baseline harness.

## Status

- **Implemented & smoke-tested (D1 + D2):** the full sweep pipeline + the 2-GPU concurrent
  grader + the static viewer run end-to-end on Qwen3-4B. A 2-per-dimension smoke run produced
  `results/report.md`, `results/metrics.json`, and `viewer/data.json`; the viewer renders all
  five views (original input, original rubrics, edited-input diffs per swept value, predicted
  footprint, actually-changed footprint) plus the qualitative + metric panels, for both D1 and
  D2. The full **30 D1 + 30 D2** run is the handed-off step (commands above).
- **Predicted vs. measured footprint:** `footprint.py` is the *a-priori* (LLM) estimator; on
  the smoke run Qwen3-4B again predicted *0* sensitive criteria — exactly why the behavioral
  **sweep** (`sweep_grade.py`) is the ground truth and `analyze.py` scores the classifier
  against it (predicted-vs-measured agreement, off-target vs. noise floor).
- **D2 caveats (small model):** rendering prose→data with a 4B model is imperfect — it can pick
  a borderline value or emit no value. Guards: a deterministic span delete, an *advisory*
  `fact_preserved` check (surfaced in the viewer, **not** auto-excluding — the bridge-invariance
  sweep is the real leak test), and the diff guard. D2 works best on facts that map to an
  unambiguous out-of-range value; "well-controlled"/qualified facts are weaker candidates.
- **Next:** run E1 at n≈30 per dimension; read `results/report.md` (kill-shot: off-target ≈
  noise floor and footprint moves); consider a stronger judge/classifier on the second GPU;
  then add D3 (severity) per idea doc §5.

## Findings

None written up yet — run the full 30+30 and summarize `results/report.md` into `reports/`.

## Data & results conventions

`data/` is git-ignored and shared with the baseline harness (see `data/README.md`). Under
`results/`, the small `report.md` / `metrics.json` / `noise_floor.json` are committable; bulk
per-item files (`shortlist.jsonl`, `variants/`, `footprint/`, `answers/`, `grades/`, `sweep/`,
`sweep_grades/`) and `viewer/data.json` are git-ignored — they contain HealthBench prompt/rubric
text, which must not be shared. `viewer/index.html` and `src/build_viewer.py` are code and sync.
