# Auto-Health-Bench

A **long-running research log** on **automating trustworthy evaluation of health LLMs** —
how we *generate*, *validate*, and *ground* the rubrics and benchmarks used to judge
medical AI answers.

This repository is organized as an evolving record of exploration, not a single
codebase or a single benchmark. It holds **idea/lit-review docs**, **paper drafts**
(Overleaf-compatible), and a growing set of **self-contained experiments** spanning
several research directions, each with its own code, environment, data, and results.

## The big picture

Evaluation is the bottleneck for trustworthy health AI. A health-LLM answer is graded
against a **rubric** — a checklist of what a good answer must contain — and the quality
of the whole field rests on those rubrics: who writes them, what they assume, and
whether they reflect how the system is actually used. Today rubrics are hand-written,
expensive, inconsistent, and pinned to a *text-only* world. We think large parts of this
can be **automated** and made **data-aware**, and that doing so both improves evaluation
and produces reusable artifacts (methods, not just datasets).

**North-star question.** Given a health-AI product or use case, can we quickly answer:
*is it already covered by an existing benchmark, or does it need a new one?* — and when it
needs a new one, can we **generate that benchmark** (tasks + rubrics, data-grounded where
relevant) largely automatically?

## Research directions

These are **parallel tracks** that start independently and **intersect** later.

### Direction A — Automatic rubric generation
*What makes a rubric good, and can we build good ones automatically?*
Rubrics define "what a good answer contains," yet writing them is slow, requires
clinical expertise, and doesn't scale. This track tackles two questions:
- **What constitutes a good rubric?** Coverage, calibration, discriminativeness,
  clinical correctness, non-redundancy — making "good rubric" a measurable target. (Open
  thread: how to set the *relative* scores between items when even experts disagree.)
- **Can we auto-generate and validate them?** Generate rubrics (or extend existing ones)
  for a health question and validate them to a quality that agrees with expert raters.
The deliverable is a reusable **rubric-generation + validation method**, not any single
benchmark. **First planned experiment:** hold out part of HealthBench, auto-generate
rubrics for it, and require that they **preserve the model ranking** the original rubrics
produce. Idea doc: [`docs/auto-rubric-generation.md`](docs/auto-rubric-generation.md).

### Direction B — Data-grounded evaluation
*Evaluate health LLMs with the user's real data, not just their typed words.*
Benchmarks like [HealthBench](https://openai.com/index/healthbench/) score models on
text-only vignettes where the only thing the model knows is what the user typed. Real
health AI runs on **ambient structured context** — wearables, labs, medications, EHR.
This track conditions evaluation on real user data and measures how the *right answer*,
the *rubric*, and the *failure modes* shift once the record is present — and how models
(mis)use that data. *(Current work: the
[`data-grounded-healthbench`](experiments/data-grounded-healthbench/) experiment; full
write-up in [`docs/vision.md`](docs/vision.md).)*

### Where they meet
Generating a **data-conditioned rubric** — one that adapts to the patient's record — is
exactly the intersection of A and B: *auto-generate a good rubric* (A) applied to *the
data changes the right answer* (B). The data-grounded experiment already prototypes this
via automatic rubric **mutation**; a dedicated rubric-generation track will generalize it.

## Repository layout

```
Auto-Health-Bench/
├── docs/                 # high-level idea docs + running literature review
│   ├── vision.md         #   Direction B idea doc (data-grounded evaluation)
│   ├── lit-review/       #   running lit-review index
│   └── *.md              #   incl. a plain-language overview for stakeholders
├── latex/                # paper drafts, Overleaf-compatible (one subfolder per project)
└── experiments/          # self-contained explorations (the actual work)
    ├── README.md         #   index + status of all experiments, by direction
    └── data-grounded-healthbench/   # experiment #1 (Direction B) — see its README
```

- **`docs/`** — the *ideas*: per-direction vision docs, design decisions, and the
  literature review. Stable, high-level, slow-changing.
- **`latex/`** — paper/manuscript sources, kept Overleaf-syncable. May hold several
  independent LaTeX projects (see [`latex/README.md`](latex/README.md)).
- **`experiments/`** — the *work*: each subfolder is one exploration with its own
  `src/`, `data/`, `results/`, and `reports/`. Different experiments may use different
  environments and datasets. See [`experiments/README.md`](experiments/README.md).

## Experiments

| Experiment | Direction | Status | Headline finding |
|---|---|---|---|
| [`data-grounded-healthbench`](experiments/data-grounded-healthbench/) | B (+ A∩B via rubric mutation) | active (Phase 1–2 done) | **~16.8%** (95% CI 14.1–20.0) of HealthBench conversations already carry the patient's own structured data, **~0%** carry wearable data. On a 30-item PoC the original rubric scored data-*aware* answers **42%** vs. a data-*blind* answer **59%**; a data-conditioned rubric restored the data-aware answer to **71%**. |

*(Direction A: no experiment yet — planned.)*

## Data & results conventions

Per experiment:

- **Raw data is not committed** — re-download or regenerate it locally via the
  experiment's `data/README.md`.
- **Large raw / intermediate result files are not committed** — they are regenerable
  from the code and data.
- **Report-style files are synced** — write-ups, method logs, score tables, and rendered
  reports (including large PDFs) travel with the repo so findings stay versioned.

## Getting started

```bash
# Python venv (shared; lives at repo root, git-ignored)
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip               # add deps as each experiment requires them

# Run an experiment — always from its own directory (scripts use relative paths)
cd experiments/data-grounded-healthbench
python3 src/rubrics/parse.py     # see this experiment's README for the full pipeline
```

See [`experiments/data-grounded-healthbench/README.md`](experiments/data-grounded-healthbench/README.md)
for the end-to-end run.
