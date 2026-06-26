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
| [`benchmark-doctor.md`](benchmark-doctor.md) | **Plain-language overview for a general audience** — the project framed as a "benchmark of benchmarks": diagnose whether an existing benchmark fits a product/model, and if not, repair it with small controlled changes that preserve expert quality. States the two core assumptions (small changes are measurable; models can perform the changes reliably) with clear reasoning, the data-setting pipeline, and a survey of how rubric-modification quality can be evaluated. The readable entry point to the three docs below. |
| [`benchmark-fit.md`](benchmark-fit.md) | **North-star methodological proposal** — benchmark *fit* as a measured invariance (the Fit Report + Fit Oracle), benchmark *generation* as graduated repair of the nearest validated benchmark (edit-distance economics), and a certification gate / chain of trust. Frames Directions A & B as instances of one general method. |
| [`counterfactual-mutation.md`](counterfactual-mutation.md) | **A∩B operator idea doc** — turn one expert task into a family by editing a single *dimension* (age, acuity, mode of disclosure, …) whose rubric **footprint is small and predictable**, so we mutate only the delta and inherit the rest of the physician rubric. Generalizes Direction B's data-axis mutation; instantiates benchmark-fit's L2 rung; makes the locality claim self-validating (bridge invariance). Five candidate dimensions + a cheap first experiment on the standing vLLM harness. |
| [`meeting-2026-06-agenda.md`](meeting-2026-06-agenda.md) | **Meeting agenda (2026-06)** — compact walk-through of the Direction-B review results, the rubric-mutation gap, the mutate-vs-rebuild argument, the framework proposal, and next steps. |
| [`lit-review/`](lit-review/) | Running literature-review index, organized by the themes the project touches. |
| [`Data-Grounded-Health-AI-Overview.md`](Data-Grounded-Health-AI-Overview.md) | Plain-language overview for non-technical stakeholders — high-level prose + aggregate numbers only (no verbatim source text). Edit this Markdown directly. |

## How this relates to the experiments

A vision doc defines *what good looks like* and *why* for its direction; each experiment
under `experiments/` implements and tests a slice of it, and writes its findings back
into the vision's framing. When an experiment changes the picture (a new number, a
refuted assumption), update the relevant vision doc so it stays the canonical statement
of the idea.
