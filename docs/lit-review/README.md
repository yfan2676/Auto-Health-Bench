# Literature review

A running, living index of the literature this project builds on. Add entries as you
read; promote the strongest ones into the related-work section of the paper draft under
[`../../latex/`](../../latex/).

The index now spans **both research directions**:

- **Direction A — automatic rubric generation** has its own full review in
  [`auto-rubric-generation.md`](auto-rubric-generation.md) (synthesis + verified
  key-paper table + an "implications for our idea" section). Bucket map below.
- **Direction B — data-grounded evaluation** is organized by the N1–N4 themes from
  [`../vision.md`](../vision.md) §4, listed further down.

> Status: Direction A reviewed in depth (2026-06). Direction B below is a **seeded
> skeleton** — topic buckets and primary sources listed; per-paper notes still to fill in.

## Direction A — automatic rubric generation

Full review: [`auto-rubric-generation.md`](auto-rubric-generation.md). Buckets:

- **A1** — rubric/checklist-based evaluation, the paradigm (G-Eval, FLASK, Prometheus,
  CheckEval, BiGGen Bench, TICK, LLM-Rubric)
- **A2** — automatic rubric/criteria generation methods (CARMO, Auto-Rubric, RRD, CDRRM,
  ARES, RubricHub, Autorubric, AdaRubric; skeptic: "Are Checklists Really Useful?")
- **A3** — rubrics as RL reward signals (RaR, RLCF, InfiMed-ORBIT, Rubric-ARM)
- **A4** — medical/clinical rubric generation + physician disagreement (Health-SCORE,
  ClinAlign, MedDialogRubrics, LiveMedBench, MedHELM, Decomposing Physician Disagreement)
- **A5** — what makes a rubric "good" + rank-preservation & meta-evaluation (RubricBench,
  RubricEval, JudgeBench, construct validity, ranking brittleness, Kendall τ vs Spearman ρ)
- **A6** — setting item weights under expert disagreement (Auto-Rubric implicit weights,
  Plank HLV, perspectivist modeling, NUTMEG, DiADEM, Bradley-Terry/Plackett-Luce)
- **A7** — automatic benchmark/task generation (AutoBencher, BenchAgents, Auto Evol-Instruct,
  MCQG-SRefine, LiveBench, ArenaBencher)

**Headline implication:** auto-generating good *health* rubrics is already crowded as of
early 2026; the open white space is **rank-preservation as the validation yardstick**,
**weight-vs-item-set sensitivity**, and **data-conditioned rubric generation (A∩B)**. See
the review's [Implications section](auto-rubric-generation.md#3-implications--what-may-need-to-change).

## Primary benchmark & context (shared)

- **HealthBench** — [announcement](https://openai.com/index/healthbench/) ·
  [paper PDF](https://cdn.openai.com/pdf/bd7a39d5-9e9f-47b3-903c-8b847ca650c7/healthbench_paper.pdf) ·
  [arXiv:2505.08775](https://arxiv.org/pdf/2505.08775) ·
  [code: openai/simple-evals](https://github.com/openai/simple-evals/blob/main/healthbench_eval.py)
- **HealthBench Professional** —
  [OpenAI PDF](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf)
- **HealthBench in practice** — [arXiv:2509.02594](https://arxiv.org/html/2509.02594v2)

## Direction B — data-grounded evaluation (themes N1–N4, from [`../vision.md`](../vision.md) §4)

### N1 — Construct validity & leakage
*Is the test fair when we synthesize the data to fit the question?*
- Counterfactual / controllable clinical-record synthesis — _to add_
- Construct validity in benchmark design — _to add_
- Dataset shortcut features / spurious cues ("Clever Hans") — _to add_
- Contamination & leakage critiques — _to add_

### N2 — Missing/noisy data, abstention & graceful degradation
*Correct use is a policy over data states, not a single answer.*
- Robustness to missing / noisy features — _to add_
- Selective prediction / abstention & calibration — _to add_
- Uncertainty-aware & conflicting-evidence clinical decision support — _to add_

### N3 — Relevance under a full record (long context)
*Find the decision-relevant fields amid distractors.*
- Long-context distractor robustness / needle-in-a-haystack / lost-in-the-middle — _to add_
- Retrieval-augmented generation over clinical notes — _to add_
- Clinical information extraction — _to add_

### N4 — Numeric & wearable time-series grounding
*Read trends, units, and noise in sensor streams.*
- LLMs for time-series & numeracy — _to add_
- Wearable-signal interpretation — _to add_
- Serialization of numeric data for LLMs; tool-use / code-execution for computation — _to add_

## Datasets referenced

- [Synthea](https://github.com/synthetichealth/synthea) (the project's data source) ·
  [All of Us](https://www.researchallofus.org/data-tools/data-sources/) ·
  [MIMIC-IV](https://physionet.org/content/mimiciv/)
- [Fitbit data in All of Us (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9811842/) ·
  [wearables dataset, Nature Medicine](https://www.nature.com/articles/s41591-026-04352-3)

## How to add an entry

For each paper, capture: **citation**, **1-line claim**, **why it matters here** (which
RQ/N it informs), and **how we use it** (motivation / method / baseline / threat). Keep
it short; depth goes into the paper draft.
