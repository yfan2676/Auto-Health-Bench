# Auto-Health-Bench

A **long-running research log** for work on *data-grounded health-AI evaluation* —
extending OpenAI's [HealthBench](https://openai.com/index/healthbench/) from text-only
vignettes to evaluations **conditioned on real longitudinal user data** (wearables + EHR).

This repository is organized as an evolving record of exploration, not a single
codebase. It holds **idea/lit-review docs**, **paper drafts** (Overleaf-compatible),
and a growing set of **self-contained experiments**, each with its own code,
environment, data, and results.

## The thesis in one paragraph

HealthBench scores models on free-text health conversations where *the only thing the
model knows is what the user typed*. Real health AI runs on **ambient structured
context** — wearable streams, medications, labs, problem lists. The moment that context
is present, the "right answer," the rubric, and the failure modes all change, in ways a
text-only benchmark cannot measure. We (a) quantify how much HealthBench's ideal answers
and rubrics shift under data-conditioning, (b) build a taxonomy of how models (mis)use
structured data, and (c) build an automated pipeline that generates data-grounded eval
items and rubrics. **Full vision: [`docs/vision.md`](docs/vision.md).**

## Repository layout

```
Auto-Health-Bench/
├── docs/                 # high-level idea docs + running literature review
│   ├── vision.md         #   the full project idea (motivation, RQs, pipeline, roadmap)
│   ├── lit-review/       #   running lit-review index
│   └── *.docx            #   plain-language overview for stakeholders
├── latex/                # paper drafts, Overleaf-compatible (one subfolder per project)
└── experiments/          # self-contained explorations (the actual work)
    ├── README.md         #   index + status of all experiments
    └── data-grounded-healthbench/   # experiment #1 — see its README
```

- **`docs/`** — the *ideas*: the vision, design decisions, and the literature review.
  Stable, high-level, slow-changing.
- **`latex/`** — paper/manuscript sources, kept Overleaf-syncable. May hold several
  independent LaTeX projects (see [`latex/README.md`](latex/README.md)).
- **`experiments/`** — the *work*: each subfolder is one exploration with its own
  `src/`, `data/`, `results/`, and `reports/`. Different experiments may use different
  environments and datasets. See [`experiments/README.md`](experiments/README.md).

## Experiments

| Experiment | Status | Headline finding |
|---|---|---|
| [`data-grounded-healthbench`](experiments/data-grounded-healthbench/) | active (Phase 1–2 done) | **~16.8%** (95% CI 14.1–20.0) of HealthBench conversations already carry the patient's own structured data, **~0%** carry wearable data. On a 30-item PoC the original rubric scored data-*aware* answers **42%** vs. a data-*blind* answer **59%**; a data-conditioned rubric restored the data-aware answer to **71%**. |

## Data & sharing policy

HealthBench carries a *"do not share examples online to prevent leakage"* notice.
Per experiment:

- **Raw data** (`experiments/*/data/`) and **large generated artifacts** (PDFs, HTML,
  per-case prompt/response/grade dumps) are **git-ignored**. Re-download raw HealthBench
  via the experiment's `data/README.md`.
- **Small report files** (method-log markdown, score matrices, shortlists) **are
  committed** so findings travel with the repo.

> ⚠️ Some committed report files (e.g. `shortlist.md`, `report.md`) embed verbatim
> HealthBench text. **Keep this repository private** unless those files are scrubbed.

## Getting started

```bash
# Python venv (shared; lives at repo root, git-ignored)
python3 -m venv .venv && source .venv/bin/activate
pip install python-docx          # add deps as experiments require them

# Run an experiment — always from its own directory (scripts use relative paths)
cd experiments/data-grounded-healthbench
python3 src/rubrics/parse.py     # see this experiment's README for the full pipeline
```

See [`experiments/data-grounded-healthbench/README.md`](experiments/data-grounded-healthbench/README.md)
for the end-to-end run.
