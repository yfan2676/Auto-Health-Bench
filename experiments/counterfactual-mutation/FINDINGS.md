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

## Where this is going — a research program

*This section steps back from the 4B pilot and frames the work as a contribution: what is
new, what the next experiment must show, and what would falsify the idea. Plain claims,
honestly bounded.*

### One idea, two uses

Counterfactual dimensional mutation is a single operation — *edit one dimension of a
HealthBench task and predict, per criterion, which parts of the physician rubric should
change* — that does two jobs at once:

- **Build.** The criteria predicted *unchanged* (the **bridge**) stay valid verbatim, so a
  new variant inherits most of an expensive expert rubric and only the small **footprint** is
  re-authored. New, mostly-expert-graded tasks at edit-distance cost.
- **Test.** That same per-criterion prediction is a behavioral expectation: a good model's
  answer should change exactly on the footprint and hold on the bridge. Measuring where it
  *actually* moves grades the model's **counterfactual consistency**.

The rubric is the shared ground truth for both. That coupling — *the structure that lets you
reuse the rubric is the same structure you test the model against* — is the core of the idea.

### What's actually new (positioned against prior work)

Perturbing a clinical LLM and watching what changes is an active area, and we don't claim
that part is new. CheckList (Ribeiro et al., 2020) named the two test shapes we use —
**invariance** (output shouldn't change) and **directional** (output should change a known
way). Metamorphic fairness testing and recent medical-counterfactual work (DeVisE,
MedPerturb, MedEqualQA, FairMedQA; 2025) perturb demographics or vitals and measure whether
the *answer* shifts, almost always expecting invariance on a protected attribute.

Two things here are new:

1. **The expected change is read off a physician rubric, per criterion.** Prior work
   hand-writes one invariance/directional expectation per input. Here one edit yields a
   *vector* of expert-authored expectations — every rubric criterion is independently a bridge
   (invariance) or footprint (directional) test, for free, from an artifact that already
   exists. The ground truth for "what should change" is the rubric, not our assertion.
2. **The same locality structure builds the benchmark.** Because the bridge is
   predicted-invariant, those criteria are reused verbatim to manufacture a new graded item;
   only the footprint is re-authored. Evaluation and validated data-augmentation become the
   same operation. The fairness-testing papers only *test* — none turn the locality into new
   expert-graded items.

A consequence the whole-answer bias metrics can't reach: we separate **appropriate
adaptation** (the footprint *should* move — age changes dosing) from **unwarranted variation**
(the bridge *should* hold — empathy shouldn't depend on age) inside one framework, because the
rubric says which is which. "It changed" becomes "it changed where it should / shouldn't."

### What the pilot settled, and what it can't

The 4B pilot proved the machinery runs end-to-end and produces an honest, floor-corrected
signal — and it surfaced a real capability gap (disclosure / numeracy, +5.7%). But every role
(predict, edit, answer, judge) was one small model, so:

- the dimension signal sits inside a **~27% same-input floor** (a 4B's run-to-run answer
  variance), which swallowed age; and
- the a-priori footprint classifier is **near chance** (on-target ≈ off-target).

Both are model-capability artifacts, not verdicts on the method. The pilot is a *feasibility*
result; the contribution needs a capable model.

### The next experiment (the immediate task)

Two changes, each aimed at one pilot limitation:

1. **A capable model, with roles split.** Use a strong model as the **footprint-predictor and
   edit-author** (the job the 4B did worst), and put a **suite of answer models** (strong →
   small) *under test*. A stronger answer model shrinks the floor so the net effect is legible;
   the role split turns "does this model adapt appropriately?" into a clean per-model number
   instead of a confound.
2. **More dimensions.** Add **D3 severity**, **D4 pregnancy**, **D5 comorbidity** (idea doc
   §5), plus one **protected-attribute** dimension (sex) whose expectation is pure
   bridge-invariance — that one engages the fairness literature directly and yields a bias
   surface.

**Deliverable: a dimension × rubric-axis sensitivity map, across models** — which axes each
dimension moves, which stay bridge, and which models adapt on the footprint while holding the
bridge. That map is a model property no leaderboard reports, and it doubles as the
per-dimension trust record (footprint precision/recall) for the build half.

| Dim | Edit | Should move (footprint) | Stays (bridge) | Status |
|---|---|---|---|---|
| D1 age | swap stated age | differentials, screening, dosing | empathy, safety-netting, work-up | done (pilot) |
| D2 disclosure | fact stated → fact as data | read/interpret the value; stop asking for it | whole management plan | done (pilot) |
| D3 severity | mild → acute descriptor | triage, ER-referral, red flags | education, history-taking | next |
| D4 pregnancy | toggle pregnant on/off | teratogen avoidance, imaging caution, involve OB | symptom-management plan | next |
| D5 comorbidity | + CKD / warfarin / allergy | interaction, contraindication, dose-adjust | primary work-up | next |
| Dx sex (control) | swap patient sex | only where clinically real | the rest — a pure invariance test | next |

### What would falsify it

Stated up front, because the next experiment is meant to *find out*, not to confirm:

- **If the bridge doesn't hold even with a strong predictor and answer model** (off-target ≈
  on-target), the locality hypothesis fails — the build half collapses and the test half loses
  its "should / shouldn't" anchor.
- **If footprint precision/recall stays near chance with a capable predictor**, the cheap
  a-priori prediction isn't usable. (The measured behavioral sweep still works as ground truth,
  but the edit-distance economics weaken — you'd need the sweep, not a one-shot prediction, to
  localize the footprint.)
- **If the net effect stays inside the floor for a capable answer model**, the dimension is a
  true bridge for that model — a real, if negative, result, and exactly the equity signal when
  it happens *only* on the bridge.

A dimension's worth is its *measured* footprint precision/recall and net effect — reported per
model, never assumed. That honesty is the point: the method earns trust dimension by dimension
instead of asserting it.

### Why this is useful in any case

A fair question: what do we actually *get* when this is done — and is it worth it whether or
not the locality hypothesis holds? The point is that the experiment doesn't bet on one outcome.
It converts a benchmark **level** — "model M scores X on HealthBench" — into a **sensitivity
map**: how M's graded behavior moves when one clinically-meaningful variable changes and
nothing else does. The level tells you how good the model is; the sensitivity tells you **how
much to trust that level, and where it breaks under the kind of framing shift that happens
constantly in real use**. A single leaderboard point hides this — a model whose graded behavior
swings on a one-line, clinically-irrelevant reframing is not as trustworthy as its score
suggests.

**Every outcome is informative — the design can't return "no signal."**

| we observe | what it means | who it's for |
|---|---|---|
| bridge holds, footprint moves the right way | locality confirmed | the benchmark builder — cheap, certified expansion |
| bridge holds, footprint stays flat | model fails to adapt where it should (same advice at 8 and 72) | model builders — a capability gap |
| bridge breaks on a clinically-irrelevant change | unwarranted variation | fairness / equity — a clean bias finding |
| bridge breaks because the edit really ripples | the dimension isn't local | us — demote it, don't mutate along it |

**Three durable outputs, beyond this paper:**

1. **A per-dimension locality ledger** — measured footprint precision/recall + net effect per
   dimension. It tells the broader Auto-Health-Bench program which dimensions are cheap to
   *mutate-and-inherit* and which need fresh rubric work — the repair-ladder cost model made
   concrete (validation scales with edit distance, not benchmark size). A *negative* locality
   result is just as useful: it says "don't expand cheaply along this axis."
2. **A per-model counterfactual-consistency profile** — does a model track the variables it
   *should* (age, severity, comorbidity, pregnancy) and stay invariant on the ones it
   *shouldn't* (protected attributes; prose-vs-data framing of the same fact)? No current
   leaderboard reports this, and it is actionable for model builders. The disclosure / numeracy
   gap found here is the first worked instance — and it is deployment-relevant precisely because
   real clinical data arrives as **values, not sentences**, so a model that reads a number worse
   than the equivalent prose will underperform exactly where it is deployed.
3. **A clean bias surface** — because the bridge is *supposed* to be invariant, any degradation
   on it across a protected attribute is unwarranted variation, cleanly separated from the
   *appropriate* change in the footprint. Most fairness metrics can only say "the output
   changed"; this says "it changed where it shouldn't have."

And the pipeline is a **reusable instrument**: a new model or a new benchmark can be run through
it to get the same map. So even the weakest result — a dimension that turns out non-local, or a
model that's flat where it should adapt — adds a row to a ledger that keeps its value after this
experiment closes.
