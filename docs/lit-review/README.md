# Literature review

A running, living index of the literature this project builds on. Organized by the
themes that the study directions in [`../vision.md`](../vision.md) §4 connect to. Add
entries as you read; promote the strongest ones into the related-work section of the
paper draft under [`../../latex/`](../../latex/).

> Status: **seeded skeleton** — topic buckets and primary sources are listed; per-paper
> notes are still to be filled in.

## Primary benchmark & context

- **HealthBench** — [announcement](https://openai.com/index/healthbench/) ·
  [paper PDF](https://cdn.openai.com/pdf/bd7a39d5-9e9f-47b3-903c-8b847ca650c7/healthbench_paper.pdf) ·
  [arXiv:2505.08775](https://arxiv.org/pdf/2505.08775) ·
  [code: openai/simple-evals](https://github.com/openai/simple-evals/blob/main/healthbench_eval.py)
- **HealthBench Professional** —
  [OpenAI PDF](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf)
- **HealthBench in practice** — [arXiv:2509.02594](https://arxiv.org/html/2509.02594v2)

## Theme buckets (from vision §4 "lit hooks")

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
