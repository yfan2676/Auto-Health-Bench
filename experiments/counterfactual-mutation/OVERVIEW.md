# Counterfactual Dimensional Mutation — overview

*A 2-3 minute read. Full run instructions: [`README.md`](README.md). Motivation: [`../../docs/counterfactual-mutation.md`](../../docs/counterfactual-mutation.md).*

## The question

A HealthBench item is a conversation `V` plus a physician **rubric** `R` (a list of scored
criteria). Writing a *new* good item means writing a *new* good rubric — the expensive,
expertise-bound step. But many new items are **one controlled edit away** from an existing
one: the same case *for a 70-year-old instead of a 30-year-old*, or *with the blood pressure
shown as a reading instead of stated as "hypertension."*

For such edits, **most of the rubric is still exactly right** — empathy, safety-netting, and
clear explanation don't care about the patient's age. Only a **predictable handful** of
criteria are touched. We call them:

- **footprint** — criteria whose correct verdict *changes* under the edit
- **bridge** — criteria whose correct verdict is *unchanged* (reused verbatim)

**Locality hypothesis:** for a well-chosen *dimension*, the footprint is small and predictable,
so we can mutate just the footprint and inherit the rest of the expert rubric — a new,
mostly-validated task at *edit-distance* cost. This experiment **measures** whether that holds.

## The core trick (why it's cheap and trustworthy)

Hold **one model answer `A` fixed** and grade it twice — under the original `V` and under the
edited `V′`. Because the answer is identical, **any verdict change is caused by the edit**, not
by a different answer. No physician needed: a criterion that *doesn't* move certifies itself.

```
        original V                         edited V′  (one variable changed)
            │                                  │
            │           same fixed answer A     │
            ▼                                   ▼
     grade A under V  ──────compare──────  grade A under V′       (judge at temperature 0)
            │                                   │
            └─ verdict unchanged  → BRIDGE   (criterion independent of the variable)
               verdict flipped    → FOOTPRINT (criterion depends on the variable)
```

We do this not for one edit but a **sweep** of K≈3 values (e.g. ages 8 / 50 / 72). A criterion
that stays put across the *whole* sweep is bridge; one that flips at *any* value is footprint
(and we record *where* it flipped). This behavioral footprint is the **ground truth** we score
the cheap a-priori LLM prediction against.

## Pipeline & data flow

```
 HealthBench full split (data/healthbench_full.jsonl)
        │
 ┌──────▼─────────┐  detect items fit for a dimension (age / disclosure)
 │  pick.py       │ ───────────────────────────────────────► results/shortlist.jsonl
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  make K≈3 single-dimension edits  V₁…V_K  (+ diff guard)
 │  sweep.py      │ ───────────────────────────────────────► results/sweep/<id>.json
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  LLM predicts which criteria SHOULD change (a-priori footprint)
 │  footprint.py  │ ───────────────────────────────────────► results/footprint/<id>.json
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  target model answers the ORIGINAL V once → fixed answer A
 │  answers.py    │ ───────────────────────────────────────► results/answers/<id>.json
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  grade A under V and each V_k  (T=0 judge, fanned across 2 GPUs)
 │  sweep_grade.py│  changed = verdict flips at ANY value ──► results/sweep_grades/<id>.jsonl
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  judge flip-rate on identical input (the comparison baseline)
 │  noise_floor.py│ ───────────────────────────────────────► results/noise_floor.json
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  join predicted vs. measured → precision/recall, off-target vs. floor
 │  analyze.py    │ ───────────────────────────────────────► results/{metrics.json, report.md}
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  aggregate everything + precompute diff highlights
 │  build_viewer.py│ ──────────────────────────────────────► viewer/data.json
 └──────┬─────────┘                                                │
        │                                              viewer/index.html (static, no deps)
        └────────────────────────────────────────────► python3 -m http.server -d viewer 8080
```

Every step is **resumable** (per-item files, skip-existing). Grading fans the many independent
judge calls across two vLLM servers (`HB_JUDGE_BASE_URLS=…:8000,…:8001`) — ~10× the serial rate.

## What the numbers mean

| Metric | Reads as |
|---|---|
| **off-target change rate** | bridge criteria that moved — should sit at the **noise floor**; if so, the bridge holds |
| **on-target rate / recall** | footprint criteria that actually moved |
| **footprint precision / recall** | did the a-priori LLM prediction match the measured sweep? (E1b headline) |
| **judge-noise floor** | how often the T=0 judge flips on *identical* input — the baseline we compare against, never zero |

Per-criterion confusion (predicted-sensitive × actually-changed) drives the viewer's coloring:
**TP** predicted+moved · **FP** bridge leaked (off-target) · **FN** footprint missed · **TN** held.

## The two dimensions

- **D1 — age / life-stage.** Pure text edit (swap the stated age). Cheapest; rich footprint
  (age-specific differentials, screening, dosing).
- **D2 — mode of disclosure.** Re-encode a *stated fact* as *data* — "I have hypertension" →
  "150/95 mmHg" — holding the clinical fact constant. The cleanest control: the whole
  management rubric is bridge; only "stop asking for the value" (moot) and "interpret the
  value" (induced) criteria should move.

New dimensions plug into `src/dimensions/` (implement detect / values / edit / footprint-prompt);
everything downstream is dimension-agnostic.

## Viewing results

`python3 src/build_viewer.py` then open **http://localhost:8080**. Per sample you see: the
original input, the original rubrics, each **edited input with changes highlighted**, the
**predicted** footprint, the **actually-changed** footprint (with per-value verdicts), and the
qualitative (judge explanations) + metric panels — filterable by dimension.
