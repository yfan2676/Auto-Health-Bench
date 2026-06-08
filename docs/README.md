# docs — ideas & literature

High-level, slow-changing material: per-direction vision docs and the running literature
review. The project's overall goal and its research directions (A — automatic rubric
generation; B — data-grounded evaluation) are stated in the
[top-level README](../README.md). The fast-moving execution work lives under
[`../experiments/`](../experiments/).

## Contents

| File | What it is |
|---|---|
| [`vision.md`](vision.md) | **Direction B idea doc** (data-grounded evaluation) — motivation, research questions, the data-conditioned evaluation method, study directions (N1–N4), opportunities, risks, datasets, pipeline, phase plan, and resolved decisions. The deepest write-up so far. |
| [`auto-rubric-generation.md`](auto-rubric-generation.md) | **Direction A idea doc** (automatic rubric generation) — what makes a rubric good (measurable properties + the open question of relative item scoring), generating tasks at HealthBench quality, and the actionable first experiment (rank-preserving rubric generation on held-out HealthBench). Seeded from the 2026-06-05 meeting. |
| [`lit-review/`](lit-review/) | Running literature-review index, organized by the themes the project touches. |
| [`Data-Grounded-Health-AI-Overview.md`](Data-Grounded-Health-AI-Overview.md) | Plain-language overview for non-technical stakeholders — high-level prose + aggregate numbers only (no verbatim source text). Edit this Markdown directly. |

## How this relates to the experiments

A vision doc defines *what good looks like* and *why* for its direction; each experiment
under `experiments/` implements and tests a slice of it, and writes its findings back
into the vision's framing. When an experiment changes the picture (a new number, a
refuted assumption), update the relevant vision doc so it stays the canonical statement
of the idea.
