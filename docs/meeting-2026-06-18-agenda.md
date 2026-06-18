# Agenda — Counterfactual dimensional mutation: results & next step (2026-06-18)

> Background links for anyone who wants the details:
> [experiment overview](../experiments/counterfactual-mutation/OVERVIEW.md) ·
> [findings](../experiments/counterfactual-mutation/FINDINGS.md) ·
> [idea doc](counterfactual-mutation.md) ·
> [live results](../experiments/counterfactual-mutation/results/report.md)

## 1. The question

A HealthBench item is a conversation plus a physician **rubric** — a list of scored
criteria that says what a good answer should contain. Writing a *new* good item means
writing a *new* good rubric, the expensive expert step. But many useful new items are **one
controlled edit away** from an existing one: the same case for a 20-year-old instead of a
70-year-old, or with the blood pressure shown as a reading instead of stated as
"hypertension." When you change one such **dimension**, only a predictable handful of
criteria should change (the **footprint**); the rest still apply unchanged (the **bridge**).

This is the **locality hypothesis**, and it is worth testing because it buys two things from
one operation:

- **Build.** If the bridge holds, a new variant inherits most of the expert rubric verbatim
  and only the small footprint is re-authored — new, mostly-expert-graded tasks at
  edit-distance cost.
- **Test.** The same per-criterion prediction is a behavioral expectation: a good model
  should change its answer exactly on the footprint and hold on the bridge. Where it
  actually moves measures the model's **counterfactual consistency** — and a bridge criterion
  that silently drops (empathy gets worse for the older patient) is an equity signal, cleanly
  separated from the *appropriate* change in the footprint.

The rubric is the shared ground truth for both. This run is the first end-to-end test of
whether the hypothesis holds at all.

## 2. Setup — what we ran

Two dimensions, chosen cheapest-first:

- **D1 — age / life-stage.** A pure text edit: swap the stated age across a life-stage grid
  (8 / 30 / 50 / 72). No data synthesis, rich expected footprint (age-specific differentials,
  screening, dosing).
- **D2 — mode of disclosure.** Re-encode a *stated fact* as *data* while holding the clinical
  fact constant — "I have hypertension" becomes "150/95 mmHg." The cleanest control: the whole
  management rubric should be bridge; only "stop asking for the value" and "interpret the
  value" criteria should move.

**Design — probe the answer model, keep the judge simple.** For every input (the original and
each edited variant) the answer model writes a **fresh answer**, and each answer is graded
against the **original** rubric, criterion by criterion, with a temperature-0 judge that only
does the simple "does this answer satisfy this item?" check. A criterion "moves" when its
verdict differs between the answer to the original and the answer to an edited variant.

**The pipeline, by step** (each step named; mechanics are in the overview): *pick* eligible
items → *sweep* each into ~3 single-dimension edits → *predict* the footprint a priori (an LLM
classifier tags each criterion) → *answer* every input → *grade* each answer against the
original rubric → measure the *same-input floor* → *analyze* → *viewer*.

**The one essential correction — subtract the same-input floor.** Answers to the original and
to each variant are sampled independently, so a 4B model at temperature gives materially
different (often equally valid) answers run-to-run. Most of the raw change rate is that
answer noise, not the dimension. So we measure a **same-input floor** — regenerate several
answers to one *unchanged* input and record how often the verdict flips — and report the
honest signal as **net effect = change rate − same-input floor**, per dimension.

**Scale.** 171 items (100 age, 71 disclosure), 2,060 criterion-pairs graded, Qwen3-4B in
every role, on the 2-GPU box.

## 3. Results

**Headline — disclosure is the real effect; age is not.** Raw change rate across all criteria
is **30.2%**, but the same-input floor is **~27%**, so most of it is answer noise. Net of the
floor:

| dimension | items | raw change rate | same-input floor | **net effect** |
|---|---|---|---|---|
| age (D1)        | 100 | 28.4% | 27.0% | **+1.4%** |
| disclosure (D2) | 71  | 32.4% | 26.8% | **+5.7%** |

Disclosure moves the model **~4× more** than age. Age sits essentially *inside* its own noise
floor — at n=100 the model adapts to an age swap about as much as it varies run-to-run on the
same input.

**Where the change concentrates (by rubric axis).** Completeness moves most, communication
least — exactly the locality pattern predicted (the communication/management bridge is the
most invariant):

| axis | change rate |
|---|---|
| completeness | 38.4% |
| accuracy | 28.0% |
| context_awareness | 26.8% |
| instruction_following | 24.7% |
| communication_quality | 16.4% |

**The a-priori footprint classifier is weak on a 4B.** It does emit real predictions (~23% of
criteria flagged sensitive), but predicted-sensitive criteria move at **28.6%** vs **30.7%**
for the predicted bridge — at or below chance (footprint precision 28.6%, recall 21.5%).
By dimension it is weakly right for age (29.8% vs 27.7%) and **inverted** for disclosure
(24.5% vs 33.5%). The predicted buckets are not yet a usable shortcut.

**Eligibility.** Age is regex-deterministic — **478** eligible items. Disclosure is scarcer
than it looks: 193 regex hits in the 5,000-item split, but most are topic mentions,
third-party/clinician cases, or items that already show a value — the clean self-disclosure
pool is **~71**.

## 4. What it means — takeaways

- **Disclosure surfaces a numeracy gap.** Qwen3-4B does not reliably read a bare value
  (`HbA1c 8.1%`, `BP 150/95`) as the diagnosis it would have recognized in prose, so its
  graded behavior shifts even though the clinical fact is identical. The same case is genuinely
  harder for the model as data than as a sentence — a concrete capability finding.
- **The bridge largely holds.** Change is concentrated in completeness/accuracy and is lowest
  on communication — the management/communication rubric is the most invariant axis, which is
  what the locality hypothesis needs.
- **Scale matters — small n overstated the effect.** A first n=30/30 pass read age +6.2% /
  disclosure +8.6%; at n=100/71 both shrank toward their floors and age fell to noise. The
  larger run is the reliable one.
- **The two limits are both one-model artifacts.** The ~27% floor is a small model's
  run-to-run answer variance, and the near-chance classifier is a 4B doing the predicting.
  Neither is a verdict on the method — they are exactly what a more capable model should fix.

**Net read:** the machinery works end-to-end and gives an honest, floor-corrected signal; the
mechanism is real on disclosure and the bridge behaves as hoped — but on a 4B the signal is
modest and the cheap a-priori prediction isn't usable yet. This is a **feasibility result**,
not the headline.

## 5. Proposal and next step

Position the work as **one operation with two uses** (build cheap expert-graded variants /
test counterfactual consistency), with the per-criterion physician rubric as the shared ground
truth — the part that distinguishes it from the crowded demographic-perturbation literature
(CheckList, DeVisE, MedPerturb, MedEqualQA), which perturbs the input and watches the *whole
answer*, and only tests, never builds.

The next experiment targets the two limits above directly:

1. **A capable model, with roles split.** Use a strong model as the **footprint-predictor and
   edit-author** (the job the 4B did worst), and put a **suite of answer models** (strong →
   small) *under test*. A stronger answer model shrinks the floor so the net effect is legible;
   the split turns "does this model adapt appropriately?" into a clean per-model number.
2. **More dimensions.** Add severity (with a monotonicity sanity check), pregnancy, and a
   comorbidity toggle, plus one protected-attribute control (sex) whose expectation is pure
   bridge-invariance — the cleanest bias surface and the direct tie to the fairness literature.

**Expected outputs:** a **dimension × rubric-axis sensitivity map across models** — which axes
each dimension moves, which stay bridge, and which models adapt on the footprint while holding
the bridge (a property no leaderboard reports) — plus a per-dimension footprint
precision/recall trust record for the build half.

**What would kill it, stated up front:** if the bridge does not hold even with a strong
predictor and answer model, the locality hypothesis fails and the build half collapses; if
footprint precision/recall stays near chance with a capable predictor, the cheap one-shot
prediction is out (the measured sweep still works, but the edit-distance economics weaken). The
next run is designed to find this out, not to assume it.

## 6. What we learn either way (why finishing it is worth it)

The reason to finish this isn't that we expect the locality hypothesis to hold. It's that the
experiment turns a benchmark **level** — "model M scored X on HealthBench" — into a
**sensitivity map**: how M's graded behavior moves when we change one clinically-meaningful
variable and nothing else. A level tells you how good a model is; the sensitivity tells you
**how much to trust that level and where it will break in deployment**. A single leaderboard
point hides this — a model whose graded behavior swings on a one-line, clinically-irrelevant
reframing is not as trustworthy as its score suggests. And every outcome of the map is
informative; the design cannot return "no signal":

- **Bridge holds, footprint moves the right way** → locality confirmed. We get cheap,
  certified benchmark expansion (inherit the bridge, re-author the footprint) *and* a clean
  measure of whether the model adapts.
- **Bridge holds, footprint stays flat** → the model fails to adapt where it should — same
  advice for an 8- and a 72-year-old, no change when severity escalates. A capability gap,
  actionable for model builders.
- **Bridge breaks** → either the model degrades on something that shouldn't depend on the
  variable (an **equity/bias** finding — worse care for the older patient, not different care),
  or the dimension simply isn't local (**demote it**). Both are real results.

So a finished run leaves three durable things, useful beyond this paper:

1. **A per-dimension locality ledger** (measured footprint precision/recall + net effect) — it
   tells the broader project which dimensions are cheap to *mutate-and-inherit* and which need
   fresh rubric work. That is the repair-ladder cost model made concrete; a *negative* result
   is just as useful, since it says "don't expand cheaply along this axis."
2. **A per-model counterfactual-consistency profile** — does a model track the variables it
   should (age, severity, comorbidity) and stay invariant on the ones it shouldn't (protected
   attributes, prose-vs-data framing of the same fact)? No leaderboard reports this. The
   disclosure/numeracy gap is the first worked example, and it matters in deployment precisely
   because real clinical data arrives as **values, not prose**.
3. **A clean bias surface** — because the bridge is *supposed* to be invariant, any degradation
   on it across a protected attribute is unwarranted variation, separated from appropriate
   clinical adaptation. A fairness signal that is hard to argue with.

And the pipeline itself is a reusable instrument: any future model or benchmark can be run
through it to get the same map.
