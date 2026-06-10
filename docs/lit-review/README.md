# Literature review

A running, living index of the literature this project builds on. Add entries as you
read; promote the strongest ones into the related-work section of the paper draft under
[`../../latex/`](../../latex/).

The index now spans **both research directions**, each with its own full review:

- **Direction A — automatic rubric generation** —
  [`auto-rubric-generation.md`](auto-rubric-generation.md) (synthesis + verified
  key-paper table + an "implications for our idea" section). Bucket map below.
- **Direction B — data-grounded evaluation** —
  [`data-grounded-evaluation.md`](data-grounded-evaluation.md) (same structure; buckets
  B1–B6, where **B2–B5 map one-to-one to the N1–N4 themes** from
  [`../vision.md`](../vision.md) §4). Bucket map below.

> Status: both directions reviewed in depth (2026-06). Verified key-paper tables and an
> "implications / gap + plan" section live in each review.

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

## Direction B — data-grounded evaluation

Full review: [`data-grounded-evaluation.md`](data-grounded-evaluation.md). Buckets
(B2–B5 ↔ the N1–N4 themes in [`../vision.md`](../vision.md) §4):

- **B1** — the competitor landscape: data-grounded / EHR-conditioned clinical LLM eval
  (MedAlign, MedAgentBench, AgentClinic, EHRSHOT, EHRNoteQA, PH-LLM, MedCalc-Bench; rubric
  near-neighbors: Adaptive Precise Boolean rubrics, Health-SCORE)
- **B2** (= N1) — construct validity & leakage (Construct-Validity reviews, shortcut/Clever-Hans,
  hypothesis-only & record-only probes, counterfactually-augmented data, label-leakage-in-healthcare,
  synthetic-eval easiness)
- **B3** (= N2) — missing/noisy data, abstention & graceful degradation (MediQ, AbstentionBench,
  CLAMBER, Q4Dx, MADAM-RAG/RAMDocs, DriftMedQA, informative-missingness, calibration & hallucination)
- **B4** (= N3) — relevance under a full record / long context (Lost-in-the-Middle, GSM-IC, RULER,
  RGB, MedDistractQA, MedOdyssey, RAG-vs-long-context-over-EHRs, clinical IE)
- **B5** (= N4) — numeric & wearable time-series grounding (PH-LLM, Health-LLM, PHIA, OpenTSLM,
  HEARTS, LLMTime, VL-Time, NumericBench, Program-of-Thoughts)
- **B6** — the synthetic-data engine: Synthea (+ its validity study), synthetic-EHR scoping review,
  HiSGT, LLM patient simulators (PatientSim/AIPatient), Polyjuice, MedAgentBench-as-eval-precedent

**Headline implication:** evaluating health LLMs *with* patient data is crowded, and
instance-specific medical rubric *generation* is crowding fast — but **rubric *mutation*
conditioned on an injected real record** (criteria become moot / new data-grounded criteria
induced / urgency flipped) is the open **A∩B** white space, alongside the **policy-over-data-states**
(graceful-degradation) framing. See the review's
[Implications section](data-grounded-evaluation.md#3-implications--the-gap-and-an-actionable-plan).

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
