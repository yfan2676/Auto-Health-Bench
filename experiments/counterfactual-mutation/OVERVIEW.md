# Counterfactual Dimensional Mutation — overview

*A 2-3 minute read. Full run instructions: [`README.md`](README.md). Motivation: [`../../docs/counterfactual-mutation.md`](../../docs/counterfactual-mutation.md).*

## The question

A HealthBench item is a conversation `V` plus a physician **rubric** `R` (a list of scored
criteria). The rubric is curated for the **input** `V`, not for any particular answer — it is
the ground truth of what a good response to `V` should contain.

Many useful new items are **one controlled edit away** from an existing one: the same case
*for a 20-year-old instead of a 70-year-old*, or *with the blood pressure shown as a reading
instead of stated as "hypertension."* When you change one such **dimension**, only a
**predictable handful** of rubric criteria should change; the rest still apply unchanged:

- **footprint** — criteria whose correct satisfaction *depends on* the changed variable
- **bridge** — criteria that are *independent* of it (reused verbatim)

**Locality hypothesis:** for a well-chosen dimension the footprint is small and predictable,
so a new variant reuses most of the expert rubric at *edit-distance* cost. This experiment
**measures** which criteria actually move — by probing the answer model.

## The core idea (probe the answer model, keep the judge simple)

We **change the input, get a fresh answer from the answer model, and grade that answer against
the original rubric** — item by item. We do **not** hold one answer fixed and ask the judge to
re-grade it under the new input: the judge cannot be trusted to infer *how the correct verdict
should change* when the input changes — the **rubric**, not the judge, holds that ground truth.
So the judge only does the simple thing it is good at ("does this answer satisfy this item?"),
and the **answer model's own adaptation** is what we observe.

```
   input V  (original)                 input V_k  (one variable changed, e.g. age 70 → 20)
       │                                    │
   A = model(V)                        A_k = model(V_k)         ← answer model responds to EACH input
       │                                    │
   grade A vs rubric R                 grade A_k vs the SAME rubric R   ← judge: simple per-item check
       │                                    │
       └─────────────── per criterion, compare verdicts ───────────────┘
              verdict unchanged → criterion is input-independent (BRIDGE)
              verdict flipped   → criterion depends on the changed variable (FOOTPRINT)
```

**Worked example.** Original input states age 70; the rubric has an item *"raise concern about
age-related complications"* (a good answer at 70 should). Change the input to age 20 and
re-ask the model: its fresh answer appropriately omits old-age concerns. Graded against the
**original** rubric, that item flips 70=met → 20=not-met — so we've **identified it as
age-dependent**, and simultaneously seen the model correctly adapt. A bridge item like
"shows empathy" should stay met at both ages; if it silently drops, that's a model weakness
(an equity signal), not a rubric effect.

We do this over a **sweep** of K≈3 values (e.g. ages 8 / 50 / 72), one fresh answer per input.
A criterion that holds across the whole sweep is bridge; one that flips at any value is
footprint. *(One answer per input means a flip can include some generation randomness — read
the off-target rate against the noise floor, never against zero.)*

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
 ┌──────▼─────────┐  answer model answers EACH input — V and every V_k → fresh answers A, A_k
 │  answers.py    │ ───────────────────────────────────────► results/answers/<id>.json
 └──────┬─────────┘
        │
 ┌──────▼─────────┐  grade each fresh answer (A under V, A_k under V_k) vs the original rubric
 │  sweep_grade.py│  changed = verdict flips vs the original answer ─► results/sweep_grades/<id>.jsonl
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

Every step is **resumable** (per-item files, skip-existing). Both answer generation and grading
fan their independent calls across two vLLM servers (`HB_TARGET_BASE_URLS`, `HB_JUDGE_BASE_URLS`
= `…:8000,…:8001`) — ~2 GPUs busy instead of one.

## What the numbers mean

| Metric | Reads as |
|---|---|
| **off-target change rate** | bridge criteria that flipped — should sit near the **noise floor**; if so the bridge holds (the model answers them consistently across inputs) |
| **on-target rate / recall** | footprint criteria that actually flipped (the model adapted on the input-dependent items) |
| **footprint precision / recall** | did the a-priori LLM prediction match what the model's fresh answers actually changed? |
| **judge-noise floor** | how often the T=0 judge flips on *identical* input — the baseline we compare against (fresh answers add some generation noise on top) |

Per-criterion confusion (predicted-sensitive × actually-flipped) drives the viewer's coloring:
**TP** predicted+flipped · **FP** bridge flipped (off-target) · **FN** footprint missed · **TN** held.

## The two dimensions

- **D1 — age / life-stage.** Pure text edit (swap the stated age). Cheapest; rich footprint
  (age-specific differentials, screening, dosing, geriatric vs. pediatric concerns).
- **D2 — mode of disclosure.** Re-encode a *stated fact* as *data* — "I have hypertension" →
  "150/95 mmHg" — holding the clinical fact constant. The cleanest control: the whole
  management rubric is bridge; only "stop asking for the value" and "interpret the value"
  criteria should move.

New dimensions plug into `src/dimensions/` (implement detect / values / edit / footprint-prompt);
everything downstream is dimension-agnostic.

## Viewing results

`python3 src/build_viewer.py` then open **http://localhost:8080**. Per sample you see: the
original input, the original rubrics, each **edited input with changes highlighted**, the
answer model's **response to each input**, the **predicted** footprint, the **actually-flipped**
footprint (with per-value verdicts), and the qualitative (judge explanations) + metric panels —
filterable by dimension.
