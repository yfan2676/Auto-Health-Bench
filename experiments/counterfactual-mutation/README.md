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

## Method (probe the answer model, keep the judge simple)

**Change the input, get a fresh answer from the answer model, and grade that answer against
the original rubric** — item by item. The rubric is curated for the *input* and holds the
ground truth for how a good answer should change, so we probe the **answer model** on each
input and the judge only does the simple thing it is reliable at: "does this answer satisfy
this item?". A criterion whose verdict **flips** between `model(V)` and `model(V′)` is one whose
satisfaction *depends on* the changed variable — that both **identifies** input-dependent
criteria and **measures** whether the model adapts.

> *Example.* Original states age 70; rubric item "raise concern about age-related
> complications" → a good answer at 70 meets it. Change the input to age 20 and re-ask: the
> fresh answer appropriately omits old-age concerns, so against the **same** rubric that item
> flips to not-met — identifying it as age-dependent and showing the model adapt correctly.

Compared against an a-priori footprint prediction:

- **bridge:** criteria predicted **kept** should *not* flip across inputs (off-target rate near
  the noise floor); a bridge criterion that drops is a model weakness (an equity signal).
- **footprint:** criteria predicted **sensitive** *should* flip when the model adapts.

Together → a confusion matrix and **footprint precision/recall**. The judge runs at
**temperature 0**; because the answers to `V` and each `V_k` are sampled independently, the rubric
**score** varies run-to-run, so the reported headline is the **net score SD = sweep score SD −
same-input floor SD** (per dimension — the std-dev of the rubric score across the sweep minus across
same-input resamples; the per-criterion flip view feeds footprint precision/recall; see
[`FINDINGS.md`](FINDINGS.md)).

## Pipeline

The **sweep** path (recommended — E1b, the *measured* footprint over K~3 values) and an
interactive **viewer**:

```
src/common.py        bridge to healthbench-local-eval (llm client + GRADER_TEMPLATE) +
                     pmap (multi-GPU grading), diff helpers
src/pick.py        Step 1  pick items that state a patient age        -> results/shortlist.jsonl
src/sweep.py         Step 2  K~3-value sweep of minimal edits (+guard)   -> results/sweep/<id>.json
src/footprint.py     Step 3  a-priori per-criterion footprint prediction -> results/footprint_v*/<id>.json
                                 (versioned by classifier model; CM_FOOTPRINT_DIR, default footprint_v2_qwen3.6-27b-fp8)
src/answers.py       Step 4  fresh answer to EACH input — V and every V_k (concurrent across GPUs)
                                                                         -> results/answers_<ver>/<id>.json
src/sweep_grade.py   Step 5  grade each fresh answer vs the original rubric (T=0, concurrent across GPUs)
                                                                         -> results/sweep_grades_<ver>/<id>.jsonl
src/noise_floor.py   Step 6  same-input answer-SCORE std-dev / dim        -> results/noise_floor_<ver>.json
                                 (Steps 4-6 are the BEHAVIORAL half, versioned by answer+judge model via
                                  CM_BEHAVIOR_VERSION, default v2_qwen3.6-27b-fp8; 4B preserved as *_v1_qwen3-4b.
                                  sweep/ is model-independent, NOT versioned. run_full.sh pins v1 for the 4B serve.)
src/analyze.py       Step 7  net SCORE SD vs floor (+ per-criterion view)  -> results/{metrics.json,report.md}
src/build_viewer.py  Step 8  aggregate everything (+difflib spans)        -> viewer/data.json
viewer/index.html    dependency-free static viewer (serve with python -m http.server)
```

A criterion is in the **measured footprint** iff the model's answer flips its verdict between
the original input `V` and *any* swept input `V_k`; held across the whole sweep ⇒ bridge.
`analyze.py` scores the a-priori footprint classifier against this measured footprint, reports
the per-dimension **net score SD** (sweep score SD − same-input floor SD) as the headline plus the
per-criterion change rate, broken down by dimension and rubric axis. Each step is resumable (per-item files / appended jsonl,
skip-existing). `src/edit.py` is the deterministic age-edit primitive reused by
`src/dimensions/age.py`.

## How to run

> **Server env + porting to another cluster (incl. H100):** building the `vllm-qwen36` env (cu129
> wheel, transformers 5.x), the GPU-arch serve flags, the model/data, and **how to continue the
> partial 27B run on a new box** (which git-ignored artifacts to copy + the exact resume command) are
> all in **[`ENVIRONMENT.md`](ENVIRONMENT.md)**. The commands below assume the env already exists.

**One command (recommended).** [`run_full.sh`](run_full.sh) owns the whole lifecycle: it
starts both vLLM servers (one per GPU), waits for them to be healthy, runs the full pipeline,
and — via a `trap ... EXIT INT TERM` — **always stops the servers again when it finishes**,
whether the run succeeds, a step fails, or you hit Ctrl-C, so the GPUs are never left occupied:

```bash
cd experiments/counterfactual-mutation
python3 src/pick.py --limit 100 && python3 src/pick.py --dimension disclosure --limit 71  # once: build the shortlist
./run_full.sh                                                                              # start -> run -> stop servers
```

It logs to `run_full.log`; per-server stdout goes to `logs/vllm_<port>.log`. Tunables (env):
`VLLM_BIN` (defaults to the conda `vllm` env — it is not on `PATH`), `GPUS`/`PORTS` (default
`"0 1"`/`"8000 8001"`), `GPU_MEM_UTIL`, `MAX_MODEL_LEN`, `HEALTH_TIMEOUT`, `CM_RUN_FOOTPRINT=1`
(also run the optional footprint step), `CM_KEEP_SERVERS=1` (skip teardown), `CM_REUSE=1`
(reuse a server already up on a port). `pick.py` is intentionally **not** automated — it
curates the item set (and D2 uses subagent-authored edit overrides).

---

**Manual / step-by-step.** Start **two** vLLM servers (one per GPU — grading fans across
both) — see [`../healthbench-local-eval/data/README.md`](../healthbench-local-eval/data/README.md).
With this path you stop the servers yourself when done (`run_full.sh` does it for you):

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-4B --port 8000 --gpu-memory-utilization 0.85 --max-model-len 32768 &
CUDA_VISIBLE_DEVICES=1 vllm serve Qwen/Qwen3-4B --port 8001 --gpu-memory-utilization 0.85 --max-model-len 32768 &
```

Then **from this directory**:

```bash
export HB_BACKEND=vllm HB_TARGET_MODEL=Qwen/Qwen3-4B HB_JUDGE_MODEL=Qwen/Qwen3-4B
# fan BOTH answer generation and grading across the two servers (both run Qwen3-4B):
export HB_TARGET_BASE_URLS=http://localhost:8000/v1,http://localhost:8001/v1
export HB_JUDGE_BASE_URLS=http://localhost:8000/v1,http://localhost:8001/v1
export HB_THINK_JUDGE=0   # non-thinking judge ≈ 10x faster grading
export HB_MAX_TOKENS=16384 # thinking author/answer calls on long rubrics can exceed 8192
# deterministic judge for clean per-item grading (default CM_JUDGE_TEMP=0, CM_JUDGE_THINK=0)

python3 src/pick.py        --limit 30   # shortlist 30 age-stating items
python3 src/sweep.py                     # K~3-value sweep of edited inputs per item
python3 src/footprint.py                 # predict the footprint a priori
python3 src/answers.py                   # fresh answer to EACH input (V and every V_k)
python3 src/sweep_grade.py               # grade each fresh answer vs the original rubric
python3 src/noise_floor.py               # same-input floor, per dimension (K answers to the same input)
python3 src/analyze.py                   # -> results/report.md (change rate, net effect vs floor, by dimension)
python3 src/build_viewer.py              # -> viewer/data.json
python3 -m http.server -d viewer 8080    # open http://localhost:8080
```

**D2 (mode of disclosure)** runs on the same machinery — just pick it (it *appends* to the
shortlist, keeping the D1 rows), then run the shared steps once for both dimensions:

```bash
python3 src/pick.py --dimension disclosure --limit 30   # re-encodable stated facts (regex + LLM confirm)
python3 src/sweep.py && python3 src/footprint.py && python3 src/answers.py && python3 src/sweep_grade.py
python3 src/noise_floor.py                               # adds the disclosure same-input floor
python3 src/analyze.py && python3 src/build_viewer.py    # one report + viewer covering D1 and D2
```

Re-encoding a stated fact as a clinically faithful, in-range data value is the demanding step.
For the best edits, author them with a capable model into
`results/edits_override/<example_id>.json` — a per-style `{find, data_phrase}` written before
`sweep.py` (`DisclosureDimension.edit_one` prefers these and falls back to the 4B render).
`find` must be an exact substring of a user message; the same value is used across the styles so
only the *form* of disclosure varies.

**D3 severity / D4 pregnancy / D5 comorbidity / Dx sex (K=1, fully subagent-authored).** These
dimensions are too semantic to detect by regex, so a capable Claude subagent both DECIDES
applicability and AUTHORS the single edit (one mutated state per item, K=1 — vs K=3 for D1/D2).
Each shares the `OverrideDimension` base (`src/dimensions/_override_base.py`) and reads one file
per item from a **per-dimension subdir**, `results/edits_override/<dimension>/<example_id>.json`
(so it never collides with D2's flat files). Schema:
`{example_id, dimension, applicable, base_value, target_value, label, edits:[{find,replace}],
rationale, note}` — each `edit` a deterministic exact-substring `replace(find, replace, 1)` on a
user message; an insertion (pregnancy/comorbidity) re-emits an existing clause plus the new phrase.
The flow inverts D1/D2 (the subagent's `applicable` flag *is* the detector):

```bash
python3 src/seed_candidates.py --dimension severity --limit 45 --out <scratch>/seed  # +the other 3
# fan ~5 Claude subagents per dimension -> write results/edits_override/<dim>/<eid>.json
python3 src/validate_overrides.py                       # exact-substring + schema gate (must pass)
python3 src/materialize_shortlist.py                    # build shortlist rows from applicable overrides
python3 src/sweep.py                                    # K=1 variant per item -> results/sweep/<eid>.json
# then the shared GPU steps (footprint / answers / sweep_grade / noise_floor / analyze / build_viewer)
```

Authoring needs **no GPU**; the new mutations land in the same `sweep/` format as D1/D2, so every
downstream step picks them up off the shortlist with no further change. Authored so far (one edit
per sample, behavioral run pending): **severity 39, pregnancy 39, comorbidity 29, sex 26**.

Config knobs (env): `HB_JUDGE_BASE_URLS` (comma-separated judge URLs, one per GPU),
`CM_JUDGE_CONCURRENCY` (grading threads per endpoint, default 8), `HB_MAX_TOKENS`
(**set 16384** — the a-priori footprint author call with thinking on can exceed 8192 on items
with many rubrics), `CM_JUDGE_TEMP` (default 0), `CM_JUDGE_THINK` (0), `CM_AUTHOR_THINK` (1),
`CM_DATA_DIR`. Endpoints and the target/judge model reuse the `HB_*` vars from the baseline harness.

## Status

- **Run end-to-end on Qwen3-4B at n=100 age + n=71 disclosure.** The full sweep pipeline + the
  2-GPU concurrent grader + the static viewer produce `results/report.md`, `results/metrics.json`,
  and `viewer/data.json`; the viewer renders the input/rubric/edited-diff/measured-footprint views
  plus the qualitative + metric panels, for both dimensions. (Full sweep+grade run ≈ 54 min; the
  a-priori footprint was then classified for all 171 items, fanned across both GPUs.)
- **Headline = net score SD** (run-to-run std-dev of the rubric score): **sweep score SD − same-input
  floor SD**, per dimension. Sweep score SD ≈ **13%** for both dimensions and both models (4B/27B); the
  same-input floor *under this metric* is being regenerated (blocked on GPU 0), so the net is pending —
  see [`FINDINGS.md`](FINDINGS.md). *Legacy per-criterion flip-rate (superseded, kept in the per-criterion
  view):* 4B net age +1.4%, disclosure +5.7% — disclosure the robust effect (~4× age), a 4B numeracy gap;
  change concentrates in completeness/accuracy, the communication/management bridge most invariant.
- **A-priori footprint: versioned + classifier-swappable; the 27B makes it discriminative.**
  `footprint.py` fans its per-item calls across both GPUs and classifies every item, writing to a
  *versioned* dir (`results/footprint_v*/`, selected by `CM_FOOTPRINT_DIR`, default
  `footprint_v2_qwen3.6-27b-fp8`); `analyze.py`/`build_viewer.py` read whichever version is set, so
  classifier models can be A/B'd with **no re-grade**. With the original **Qwen3-4B** classifier
  discrimination was near chance (on-target 28.6% vs off-target 30.7%, *inverted* for disclosure).
  Re-running with **Qwen3.6-27B-FP8** (served from the isolated `vllm-qwen36` env) makes it
  **clearly positive: on-target 42.5% vs off-target 28.8% (+13.8pt), precision 42.5%**, flagging a
  more conservative 10.7% of criteria (age 43.4/25.0; disclosure stays flat — the refined prompt
  marks nearly all disclosure criteria "kept"). It feeds only footprint precision/recall — **not**
  the change-rate/net-effect headline (behavioral, identical across classifiers) — so
  `sweep_grade.py` still tolerates a missing footprint file and the step stays optional. *(The
  earlier "predicts 0 sensitive" was a JSON-extraction bug in `llm.extract_json`, since fixed.)*
- **⚠ Behavioral re-run on Qwen3.6-27B-FP8 (answer + judge) — PARTIAL.** The behavioral half
  (Steps 4–6) is versioned by answer+judge model (`CM_BEHAVIOR_VERSION`, default the 27B; 4B kept as
  `*_v1_qwen3-4b`) and re-run on the *same* `sweep/` inputs. Drivers: `run_behavioral_27b.sh` (both
  GPUs) and `complete_v2_gpu1.sh` (single-GPU finish). **GPU 0 fell off the PCIe bus during the
  same-input floor**, so v2 is incomplete: saved = 171/171 answers, 2055/2061 grades; pending = **both
  score-SD floors** + 6 ungraded criteria. Partial: sweep score SD **age 13.5% / disclosure 13.1%**
  (floor/net pending); per-criterion footprint on/off **39.4%/25.4%** (disclosure sharp 56.2%/24.7%;
  legacy flip-rate age net +2.8%). `report.md`
  carries a ⚠ partial-run banner. Finishing needs GPU 0 back (reboot) — a fresh vLLM can't boot while
  a GPU is faulted (NVML enumerates all devices). `common.judge_criterion` was hardened (extract the
  JSON object that actually carries `criteria_met`, + a thinking-on rescue) for the larger judge.
- **D2 eligibility ceiling ≈ 71 (not 100).** The regex prefilter gives 193 hits in the 5k split,
  but most are topic/class mentions, third-party/clinician cases, or questions — not re-encodable
  self-disclosures; capable authors flag ~40% unsuitable. D1 age is regex-deterministic (478
  eligible). D2 edits are authored into `results/edits_override/` (above); the 4B prose→data render
  remains a fallback with an *advisory* `fact_preserved` check + diff guard.
- **D3–Dx mutations authored (K=1, subagent-written), behavioral run pending.** Severity 39,
  pregnancy 39, comorbidity 29, sex 26 single-dimension edits live in
  `results/edits_override/<dim>/` + `results/sweep/`, on the shortlist alongside D1/D2. The GPU half
  (footprint/answers/grade/floor/analyze) hasn't been run for them yet — it will pick them up off the
  shortlist automatically. (D4/D5 footprints are mostly *induced* new criteria; sex is the
  protected-attribute invariance control — expect near-total bridge.)
- **Next:** lower the answer temperature or average several answers per input to shrink the ~27%
  floor and sharpen the net effect (important now that age sits inside the floor); to push D2 nearer
  100 include clinician/third-party specific-instance cases; run the behavioral half for D3–Dx.

## Findings

See [`FINDINGS.md`](FINDINGS.md) — the narrative + the per-dimension net effects. Live numbers
regenerate into `results/report.md` on each `analyze.py` run.

## Data & results conventions

`data/` is git-ignored and shared with the baseline harness (see `data/README.md`) — that holds the
**full original** HealthBench download, which stays local. Under `results/`, the small `report.md` /
`metrics.json` / `noise_floor.json` are committable; bulk per-item files (`shortlist.jsonl`,
`footprint/`, `answers/`, `sweep/`, `sweep_grades/`, `edits_override/`) are git-ignored to keep the
repo small. `viewer/data.json` **is committed for this experiment** so the static viewer renders on a
fresh clone: it embeds verbatim prompt/rubric/judge text for the **tested ~171-item subset**, which the
[repo-wide policy](../README.md) allows (only the full original dataset is restricted). The general
`experiments/*/viewer/data.json` ignore still guards every other experiment. `viewer/index.html` and
`src/build_viewer.py` are code and sync.

To view after a clone (the viewer `fetch`es `./data.json`, so it must be *served*, not opened
as a `file://`):

```bash
cd experiments/counterfactual-mutation
python3 -m http.server -d viewer 8080   # open http://localhost:8080
```
