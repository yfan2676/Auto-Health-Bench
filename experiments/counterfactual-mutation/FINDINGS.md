# Counterfactual Dimensional Mutation — findings

*Run: 2026-06-17. 171 items (100 D1 age, 71 D2 disclosure), Qwen3-4B for all roles. Live numbers:
[`results/report.md`](results/report.md) + the viewer. Method: [`OVERVIEW.md`](OVERVIEW.md).
This file is the narrative.*

## Setup

- **D1 (age):** swap the patient's age across a life-stage grid (e.g. 8 / 30 / 50 / 72).
- **D2 (mode of disclosure):** re-encode a stated fact as data, holding the fact constant
  ("I have hypertension" → "a blood pressure of 150/95 mmHg"). The D2 edits were authored by
  a capable model (per-style `find`/`data_phrase` overrides in `results/edits_override/`):
  exact-substring `find`, in-range diagnostic values, the same value across the 3 styles so only
  the *form* of disclosure varies.
- For every input — original `V` and each variant `V_k` — the answer model produces a **fresh**
  answer, each graded against the **original** rubric. A criterion "moves" when its verdict
  differs between the answer to `V` and the answer to some `V_k`.

## Reading the change rate: subtract the same-input floor

The raw fraction of criteria that move is **~30%**, but a 4B model at temperature gives
materially different (often equally valid) answers to the *same* input, and the answers to `V`
and each `V_k` are sampled independently — so the raw rate contains the model's own answer
variance. The baseline that isolates the dimension is the **same-input floor**: regenerate K
answers to one *unchanged* input and measure the flip rate (`noise_floor.py`). It is **~27%**.

**Net dimension effect = change rate − same-input floor** (a delta of two rates, shown as %):

| dimension | items | change rate | same-input floor | **net effect (Δ)** |
|---|---|---|---|---|
| age (D1)        | 100 | 28.4% | 27.0% | **+1.4%** |
| disclosure (D2) | 71  | 32.4% | 26.8% | **+5.7%** |

(floors estimated on a ~20-item subset per dimension.) So once its own sampling noise is
removed, **age has essentially no attributable effect** — at n=100 the model adapts to an age
swap about as much as it varies run-to-run on the *same* input, i.e. age behaves almost like a
pure bridge for this 4B model. **Disclosure stays clearly positive (~4× age).**

## What the signal looks like

- **Disclosure moves the model materially more than age** (+5.7% vs +1.4%). This is a
  **numeracy gap**: Qwen3-4B does not reliably read a bare value (`HbA1c 8.1%`, `BP 150/95`) as
  the diagnosis it stated in prose, so its graded behavior shifts — even though the underlying
  clinical fact is identical. The same case is genuinely harder for the model when the fact is
  shown as data — a useful capability finding.
- **The footprint pattern holds.** Change concentrates in **completeness** (38.4%) and
  **accuracy** (28.0%) and is lowest on **communication_quality** (16.4%) — i.e. the
  communication/management **bridge is the most invariant**, as the locality hypothesis predicts.
- **Earlier small-n caveat borne out.** A first pass at n=30/30 read age +6.2% / disclosure
  +8.6%; scaling to n=100/71 shrank both toward their floors and pulled age down to noise. The
  larger run is the reliable one: **disclosure is the robust effect; age is not.**

## D2 eligibility: the clean pool is smaller than it looks

The disclosure picker's regex prefilter yields **193 hits** in the 5,000-item split, but most are
**not re-encodable self-disclosures**: topic/class mentions ("diabetic foot ulcers", "managing
type 1 diabetes"), third-party/clinician-patient cases ("my patient has hypertension"), questions
("is that stage 1 hypertension?"), or items that already show a value. When capable models author
the edits, ~40% of regex+confirm "fits" are flagged unsuitable. The clean self-disclosure pool is
**~71**, the cap for this run. (D1 age is regex-deterministic: **478** eligible.) To push D2 nearer
100, relax to include clinician/third-party *specific-instance* cases (a valid disclosure-mode
contrast, at the cost of mixing self- and third-party disclosure in one bucket).

## Caveats / how to sharpen

- **The ~27% floor is the dominant noise source.** To raise signal-to-noise: lower the answer
  temperature, or **average several answers per input** and take the majority verdict before
  comparing. Either shrinks the floor and tightens the net effect — important given age now sits
  inside the floor.
- **The a-priori footprint classifier has little discriminative power on Qwen3-4B.** Run on all
  171 items it flags **~23%** of criteria as sensitive (real predictions, spread across the
  dimension buckets), but predicted-sensitive criteria move at **about the same rate as the
  predicted bridge** — on-target **28.6%** vs off-target **30.7%** overall (weakly positive for
  age: 29.8% vs 27.7%; *inverted* for disclosure: 24.5% vs 33.5%). So predicted-vs-measured
  agreement is near chance and the reliable footprint signal remains the measured **per-axis change
  rate** + the by-value flip distribution, not the predicted buckets. A stronger classifier model
  would be needed to make the a-priori prediction useful. *(An earlier pass reported "predicts ~0
  sensitive" — that was a JSON-extraction bug in `llm.extract_json` that returned the last inner
  object and dropped every prediction; now fixed.)*
- **Age edits currently carry only the deterministic age-number swap.** That same extraction bug
  also suppressed `edit.py`'s optional LLM *entailed-phrasing* extras, so all 300 age variants
  swap just the age number ("72-year-old" → "8-year-old") without co-varying descriptors
  ("retired" → "in school"). The primary swap is correct and disclosure edits (subagent overrides)
  are unaffected, but the **age net effect (+1.4%) is measured on less-thorough edits** — re-running
  `sweep.py` with the fixed parser would refresh the age variants and could move that number.
