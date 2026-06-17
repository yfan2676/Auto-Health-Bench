# Counterfactual Dimensional Mutation — findings

*Run: 2026-06-17. 60 items (30 D1 age, 30 D2 disclosure), Qwen3-4B for all roles. Live numbers:
[`results/report.md`](results/report.md) + the viewer. Method: [`OVERVIEW.md`](OVERVIEW.md).
This file is the narrative.*

## Setup

- **D1 (age):** swap the patient's age across a life-stage grid (e.g. 8 / 30 / 50 / 72).
- **D2 (mode of disclosure):** re-encode a stated fact as data, holding the fact constant
  ("I have hypertension" → "a blood pressure of 150/95 mmHg"). The 30 D2 edits were authored by
  a capable model (per-style `find`/`data_phrase` overrides in `results/edits_override/`):
  exact-substring `find`, in-range diagnostic values, the same value across the 3 styles so only
  the *form* of disclosure varies.
- For every input — original `V` and each variant `V_k` — the answer model produces a **fresh**
  answer, each graded against the **original** rubric. A criterion "moves" when its verdict
  differs between the answer to `V` and the answer to some `V_k`.

## Reading the change rate: subtract the same-input floor

The raw fraction of criteria that move is **~31–32%**, but a 4B model at temperature gives
materially different (often equally valid) answers to the *same* input, and the answers to `V`
and each `V_k` are sampled independently — so the raw rate contains the model's own answer
variance. The baseline that isolates the dimension is the **same-input floor**: regenerate K
answers to one *unchanged* input and measure the flip rate (`noise_floor.py`). It is **~24%**.

**Net dimension effect = change rate − same-input floor:**

| dimension | change rate | same-input floor | **net effect** |
|---|---|---|---|
| age (D1)        | 31.0% | 24.7% | **+6.2 pts** |
| disclosure (D2) | 32.4% | 23.8% | **+8.6 pts** |

(floors estimated on a ~20-item subset). So the attributable effect of changing one dimension
is **modest (~6–9 pts)** — much smaller than the raw rate alone implies.

## What the signal looks like

- **The footprint pattern holds for both dimensions.** Change concentrates in
  **completeness/accuracy** (~38–40%) and is lowest on **communication_quality** (~15–18%) —
  i.e. the communication/management **bridge is the most invariant**, as the locality hypothesis
  predicts. (D2 by-axis: completeness 40%, accuracy 30%, context 29%, instruction 22%,
  communication 18%.)
- **Disclosure moves the model *more* than age** (+8.6 vs +6.2 pts). This is a **numeracy gap**:
  Qwen3-4B does not reliably read a bare value (`HbA1c 8.1%`, `BP 150/95`) as the diagnosis it
  stated in prose, so its graded behavior shifts — strongest on completeness (it gives less
  complete management advice when it must infer the diagnosis from a number). The same case is
  genuinely harder for the model when the fact is shown as data — a useful capability finding.

## Caveats / how to sharpen

- **The a-priori footprint classifier is degenerate on Qwen3-4B** — it predicts ~0 sensitive
  criteria, so footprint precision/recall collapse. The usable footprint signal is the measured
  **per-axis change rate** and the by-value flip distribution, not the predicted buckets. A
  stronger model on the classifier would make predicted-vs-measured meaningful.
- **The ~24% floor is the dominant noise source.** To raise signal-to-noise: lower the answer
  temperature, or **average several answers per input** and take the majority verdict before
  comparing. Either shrinks the floor and tightens the net effect.
- Two D2 samples are weak by construction (a bare `"Type 2 diabetes-"` fragment; a
  clinician-to-clinician prompt about a *class* of patients); both still produced valid edits
  and are kept, flagged in their override `note`.
