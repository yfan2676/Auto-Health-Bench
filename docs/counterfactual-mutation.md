# Counterfactual Dimensional Mutation

> **Scope.** Idea doc for the **A∩B intersection** of [Auto-Health-Bench](../README.md):
> a way to turn one expert-validated task into a *family* of new tasks by editing a
> single **dimension** of the task (age, acuity, how a fact is disclosed, …) such that
> we can be **counterfactually confident the edit moves only a small, predictable subset
> of rubric items** — so we mutate just those items and **inherit the rest of the
> physician-written rubric verbatim**, preserving its expert quality.
>
> This generalizes Direction B's data-axis rubric mutation
> ([`vision.md`](vision.md) §3) to many dimensions, and it is the concrete operator for
> the **L2 "mutate criteria — only the delta"** rung of the repair ladder
> ([`benchmark-fit.md`](benchmark-fit.md) §5). The yardstick is Direction A's
> rank/verdict preservation ([`auto-rubric-generation.md`](auto-rubric-generation.md) §4).
>
> **Status:** proposal (2026-06-16). No experiment yet; the cheapest one (§7, E1) reuses
> the [`healthbench-local-eval`](../experiments/healthbench-local-eval/) vLLM harness
> already standing and needs no new data synthesis.

---

## 1. The idea in one paragraph

A HealthBench item is a conversation `V` plus a physician rubric `R` (a list of pointed
criteria). Writing a *new* good item means writing a *new* good rubric — the expensive,
expertise-bound step. But many useful new items are **one controlled edit away** from an
existing one: the same chief complaint *for a 70-year-old instead of a 30-year-old*; the
same case *where the hypertension is shown as a BP reading rather than stated*; the same
symptom *at emergency severity instead of mild*. For edits like these, **most of the
rubric is still exactly right** — empathy, safety-netting, asking about symptom
characterization, clear explanation don't care about the patient's age. Only a
**predictable handful** of criteria are touched (age-specific differentials, screening,
dosing). The proposal: **choose dimensions whose rubric footprint is small and
predictable a priori, mutate only that footprint, and keep the rest of the expert rubric
unchanged.** You get a new, mostly-expert-validated task at *edit-distance* cost — and,
as a bonus, a **minimal-pair counterfactual** (two items differing in exactly one
variable), which is a far stronger experimental object than two unrelated items.

---

## 2. Why this is the right move (and what is new)

The project already argues **mutate-don't-rebuild** ([`meeting-2026-06-11-agenda.md`](meeting-2026-06-11-agenda.md)
§3, [`benchmark-fit.md`](benchmark-fit.md) §5): rebuilding discards HealthBench's 48,562
physician-written criteria and pays full validation cost; mutating means experts check
only the delta, and **validation cost scales with edit distance, not benchmark size**.
Pairing within the same item also cancels the ~82% case-level label variance that sinks
across-benchmark comparisons.

Direction B has so far exercised **one** mutation axis — *data availability* (inject the
record; criteria that reward *asking* go moot, data-grounded criteria are *induced*,
urgency *shifts*). This doc makes two additions:

1. **A dimension is a first-class object, chosen for *locality*.** Not every edit is
   cheap. The contribution is a way to *rank candidate dimensions by how local and
   predictable their rubric footprint is*, and a shortlist of five that score high (§5).
   Locality is what licenses "mutate the delta, inherit the rest."
2. **The locality claim is made falsifiable and self-validating (§4).** "We are
   counterfactually confident only items {i,j} change" is a *testable prediction*: hold a
   model's answer fixed and re-grade it under the edited conversation — the criteria we
   predicted *unchanged* must keep their verdict (up to judge noise), and the ones we
   predicted *changed* must move. This turns "confidence" from an assertion into a
   measured precision/recall of the footprint, with **no physician needed for the easy
   half** (the unchanged criteria certify themselves by invariance; experts review only
   the small changed delta).

The relationship to existing pieces:

| Existing piece | This doc |
|---|---|
| vision.md data-axis mutation (`moot/induced/urgency/answer_shift`) | one dimension among five; reuses the same change-type vocabulary |
| benchmark-fit.md L2 "mutate only the delta" + "bridge set" | the concrete operator; **bridge = the predicted-unchanged criteria**, and §4 *measures* whether the bridge truly holds |
| auto-rubric-generation.md §3.1 "modify existing items without degrading quality" + §4 rank preservation | the quality bar; we add per-criterion **verdict** preservation on the bridge as the finer-grained check |

---

## 3. The locality hypothesis, made precise

Let an item be `(V, R)` with criteria `R = {c₁…cₙ}`. A **dimensional edit** is a
function `δ` that changes one task variable, producing `V′ = δ(V)` (e.g. age 30→70).
Define the **footprint**

```
F(δ) = { cᵢ ∈ R : the correct verdict of cᵢ differs between V and V′ }
```

and the **bridge** `B(δ) = R \ F(δ)` (criteria whose correct verdict is unchanged).

> **Counterfactual-locality hypothesis.** For a well-chosen dimension and a realistic
> edit `δ`, the footprint `F(δ)` is **(a) small**, **(b) predictable a priori** from the
> criterion text and the dimension (without running a model), and **(c) the bridge
> `B(δ)` remains clinically valid verbatim** — so `R′ = mutate(F(δ)) ∪ B(δ)` is a
> correct rubric for `V′` that reuses `|B(δ)|` expert criteria unchanged.

`F(δ)` can be estimated two independent ways: **predicted** a priori from the criterion
text (an LLM classifier — cheap, but only as trustworthy as the model) or **measured**
behaviorally by sweeping the dimension and watching which verdicts actually move (§4.1 —
the stronger ground truth). The classification vocabulary (same as the
[dependency classifier](../experiments/data-grounded-healthbench/src/dependency/classifier_prompt.md)
and [mutation spec](../experiments/data-grounded-healthbench/src/phase2/mutation_prompt.md)):
**kept** (in the bridge), or in the footprint as **moot** / **reweighted-or-rewritten** /
**induced** / **urgency-shifted** / **answer-shifted**. A dimension is "mutable with
confidence" exactly when the footprint is *small* and the predicted footprint *matches the
measured one* — which §4 quantifies.

---

## 4. Verifying the mutation — the locality claim validates itself

The crux, and the reason this is trustworthy without commissioning physicians for the
bulk of the work. Four checks, cheapest first; the first two need **no clinical judgment
at all**.

**V1 — Bridge invariance (the self-validating core).** Take any model answer `a` to the
*original* `V`. Grade `a` against each criterion under `V` and again under `V′` (same
answer, edited conversation). For every criterion we predicted **kept**, the verdict must
be identical. Define the **off-target verdict-change rate** = fraction of predicted-kept
criteria whose verdict flips. *This should sit at the judge-noise floor.* If it is high,
either the footprint prediction was wrong (the dimension rippled further than we thought)
or the dimension isn't local — **demote it**. Crucially, V1 requires only the existing
grader, never a physician: an unchanged criterion *certifies itself by invariance*.

- **Judge-noise floor** must be measured, not assumed: grade the *identical*
  `(V, a, cᵢ)` triple `K` times and record the per-criterion flip rate; or run the
  locality test with the judge at **temperature 0** (`HB_TEMPERATURE=0`) so the only
  varying input is the conversation edit. Compare V1's off-target rate against this floor
  with the noisy-judge framework, never against zero.

**V2 — On-target sensitivity.** The predicted-**footprint** criteria *should* move
(again, same fixed answer, two framings). A footprint that doesn't move means either the
edit is inert or the criterion wasn't really dimension-sensitive. V1+V2 give a confusion
matrix (predicted-change × actual-change) → **footprint precision/recall**, the headline
quality number for a dimension, computable entirely from the grader.

**V3 — Direction & monotonicity (sanity, where the dimension is ordered).** For ordered
edits (severity↑, age toward the extremes, data quality↓) the footprint should move in
the clinically expected direction, and ideally *monotonically* across a sweep. This is
the [`vision.md`](vision.md) §4 "hidden-context / monotonicity" sanity check generalized:
if escalating severity does **not** tighten the urgency criteria, the mutation (or the
grader on those criteria) is broken, not the model.

**V4 — Delta expert validation (the only physician step, and it's tiny).** Experts review
**only** `mutate(F(δ))` — the changed/added criteria — plus a calibration sample of
"kept" decisions to confirm the bridge. Report auto-vs-human agreement on the delta. This
is the [`benchmark-fit.md`](benchmark-fit.md) §6 certification gate at minimum surface:
the bridge is certified by V1 invariance + rank preservation, only the delta needs eyes.

> Net: V1–V3 are **free and run on the harness we already have**; V4 is the small,
> bounded human cost. "Counterfactually confident" becomes a measured footprint
> precision/recall plus an off-target rate at the noise floor.

### 4.1 — Predicted vs. *measured* footprint: the sweep test

The first n=2 pilot exposed a weakness in trusting a *single* LLM estimator: we used an LLM
to **predict** per-criterion sensitivity (the a-priori footprint classifier) and an LLM to
**grade**, and the small predictor called every criterion age-neutral — which we cannot
take on faith. The fix is to determine dimension-(in)dependence **behaviorally**, with a
second estimator that does *not* rely on the judge's introspective reasoning *about*
sensitivity, only on its **verdict behavior under perturbation**:

> **Sweep test.** Instead of a single edit A→B, instantiate the dimension at **K values**
> v₁…v_K (e.g. ages 18, 30, 45, 60, 75) and grade a *fixed* answer under each. A criterion
> whose verdict is **constant across the entire sweep** is dimension-**independent**
> (bridge); one whose verdict **changes at some value** is dimension-**dependent**
> (footprint) — and the sweep localizes *where* it flips (e.g. a screening cutoff near 50),
> a clinically interpretable bonus.

This is **metamorphic / invariance testing**: we assert a relation ("editing only age must
not change *this* verdict") and hunt for violations, rather than asking a model whether the
relation holds. Two properties make it the stronger *primary* detector of the footprint:

- **Model-light in the right place.** It still uses the judge to produce verdicts, but a
  criterion's classification comes from *aggregated behavior over K gradings*, not from one
  model's opinion about age. Run each sweep point ×R repeats against the **noise floor**
  (V1) and it separates real dimension-driven flips from judge jitter.
- **Confidence is quantifiable and grows with the sweep.** Invariance is *evidence of*
  independence, not proof — a truly-sensitive criterion could stay flat by luck on one
  answer. So sweep **wider** (more values spanning the clinically meaningful range) and
  over **several fixed answers** (different models/temperatures): the probability that a
  dependent criterion survives *all* of them unchanged falls fast, bounding the
  false-"independent" rate. Movement, conversely, is near-proof of dependence (modulo the
  measured noise floor).

**Two estimators, used together.** The a-priori LLM prediction and the measured sweep are
independent, so their **agreement** is the real confidence signal and their
**disagreement** is the review queue. Operationally: treat the sweep as the *empirical*
footprint, use it to **score the cheap predictor** (does the a-priori classifier match the
behavioral truth?), and mutate only criteria the sweep marks dependent — so the inherited
bridge is certified by *observed invariance across the sweep*, not by any model's say-so.
This is also the cleanest connection to the [`benchmark-fit.md`](benchmark-fit.md) §6
"counterfactual-instantiation" validity control: the sweep *is* that control, run per
criterion.

*Honest limits.* The verdict is binary, so the sweep detects **verdict-flipping**
dependence — exactly the kind that moves the score — and can miss a criterion that becomes
subtly less appropriate without flipping pass/fail (V4 delta-validation still samples the
bridge for this). Each swept value must itself be a clean single-dimension edit (the
edit-guard), and for *categorical* dimensions (pregnancy, comorbidity toggle) the "sweep"
is the toggle plus a few realistic instantiations rather than an ordered grid.

---

## 5. Five dimensions to mutate with confidence

Chosen for **high locality** (small, predictable footprint), **realism** (the edit yields
a genuine, internally-consistent case), and **coverage** of different rubric axes
(accuracy / completeness / context-awareness / communication / emergency-referral). For
each: the edit, what the footprint should be, what stays in the bridge, and the
interesting result we'd expect.

| # | Dimension | Edit `δ` | Predicted footprint (small) | Bridge (inherited) | Primary axis stressed |
|---|---|---|---|---|---|
| D1 | **Age / life-stage** | swap the stated age (e.g. 30↔70; or adult↔adolescent) | age-specific differentials, screening/prevention, red-flag thresholds, drug dosing/contraindications, pregnancy-possibility | symptom characterization, empathy, safety-netting, clear explanation, general work-up | accuracy, completeness |
| D2 | **Mode of disclosure** ("data interpretability") | re-encode a *stated fact* as *data* — "I have hypertension" → a BP table; "on metformin" → a med-list line; "sugar's been high" → an HbA1c value (**fact held constant**) | *moot*: criteria rewarding "ask/confirm the value"; *induced*: "correctly reads/interprets the value" (numeracy) | the entire clinical-management rubric (the underlying fact is unchanged) | context-awareness |
| D3 | **Symptom severity / acuity** | tune one severity descriptor (mild, exertional, 2 days → crushing, at-rest, radiating, diaphoretic, 3 weeks) | *urgency-shift*: triage/ER-referral/red-flag criteria; possibly *answer-shift* on next step | education, empathy, explanation of the condition, asking about history | emergency-referrals |
| D4 | **Pregnancy / physiological state** | toggle "8 weeks pregnant" (or breastfeeding) on/off | *induced*: teratogenic-drug avoidance, imaging/radiation caution, "involve OB"; *answer-shift*: drug/dose choice | the symptom-management plan, communication, general safety-netting | accuracy, completeness (safety) |
| D5 | **One comorbidity / medication** | add or remove a single history item — "+ CKD", "+ on warfarin", "+ penicillin allergy" | *induced*: interaction/contraindication/dose-adjustment for the primary plan (e.g. NSAID caution in CKD, bleeding on warfarin) | the primary-complaint work-up and advice | accuracy (safety) |

**Notes on the two examples you raised.**

- **D2 is the cleanest construct-validity control we have.** vision.md's data axis
  *injects new relevant data*, which invites the fair objection "you handed the model
  exactly what it needed" (vision.md N1 leakage). D2 instead **holds the fact constant
  and only changes its representation** (prose claim → structured value). So the
  *clinical content* of a correct answer is unchanged — the bridge is almost the whole
  rubric — and the *only* legitimate movers are "stop asking to confirm what's shown" and
  "interpret the number." That isolates the ask→use shift from any new-information
  confound, addressing N1 head-on. (Set-up cost is higher than D1: you must render a fact
  as plausible data; that's why §7 starts with D1.)
- **D1 (age) is the cheapest end-to-end.** It is a pure text edit — no data synthesis —
  yet it exposes a rich footprint (different risks, screening, dosing) and a clean
  equity probe (§6). That makes it the right first experiment.

**Second tier — useful but *lower* locality (state honestly, don't over-promise).**
*Sex/gender* (often re-routes the whole differential — footprint large), *user health
literacy / register* layperson↔clinician (moves mainly the communication-quality axis —
clean *axis-wise* but touches many items), *care setting / resource level* (referral-pathway
and availability criteria — the global-health theme). These are candidates once V1–V2
have calibrated how we measure locality; lead with D1–D5.

### Per-dimension detail (D1 as the worked template)

**D1 — Age.**
- *Mutate:* edit the age token and any age-entailed phrasing; for the footprint, rewrite
  age-conditional criteria to the new life-stage ("screen for X if >50" → applies/doesn't)
  and *induce* any newly-relevant ones (e.g. falls/polypharmacy at 70; pregnancy-possibility
  at 30); **keep** everything age-neutral verbatim.
- *Verify:* V1 — grade a fixed answer under both ages; age-neutral criteria must not move
  (off-target rate ≈ floor). V2 — age-specific criteria must move. V3 — shifting toward
  elderly should *induce* (not delete) geriatric considerations.
- *Expected interesting outcome:* (i) a **counterfactual-consistency profile** — does the
  model actually *re-prioritize* differentials/screening when only the age changes, or is
  it age-invariant (a real failure)? (ii) An **equity signal that separates good from bad
  adaptation**: bridge criteria *should* be invariant across ages; if a model's general
  care quality (empathy, safety-netting, explanation) silently *drops* for the 70-year-old,
  that is unwarranted bias, cleanly distinguished from the *appropriate* change in the
  footprint.

(D2–D5 follow the same template; D5's penicillin-allergy case is already worked at n=1 in
the [phase-2 PoC](../experiments/data-grounded-healthbench/reports/phase2-poc.md) — reframe
it as a *toggle* with a predicted footprint and the V1 bridge test.)

---

## 6. What we expect to find, and why it's valuable

- **A dimension × rubric-axis sensitivity map.** Which axes are sensitive to which
  dimensions (hypothesis: emergency-referrals → severity/age; context-awareness →
  disclosure mode; accuracy-safety → comorbidity/pregnancy; communication → literacy).
  This is the per-dimension analogue of the data-axis drift map and feeds the
  [`benchmark-fit.md`](benchmark-fit.md) Fit Report (which Θ-axes a benchmark is blind to).
- **Counterfactual-consistency as a new model property.** Same machinery as the
  ask/use/reconcile *data-use policy* (benchmark-fit §8.2), generalized: *does a model's
  behavior track clinically-relevant task variables it should track, and stay invariant on
  the ones it shouldn't?* "Model M ignores age; model N over-reacts to mild severity" is a
  result no current leaderboard reports, and it is **actionable** for model builders.
- **A bias surface that's hard to argue with.** Because the bridge is *supposed* to be
  invariant, off-target degradation on bridge criteria across age/sex/pregnancy is
  unwarranted quality variation — a fairness finding that doesn't conflate "treated the
  case differently because it *should* differ" with "gave worse care."
- **Cheap, certified benchmark expansion.** N counterfactual variants per seed item, each
  reusing most expert criteria → coverage and discrimination gains at edit-distance cost,
  with a per-edit trust record (footprint precision/recall + delta validation). This is
  the L2/L3 economics of benchmark-fit §5 made concrete and measured.

---

## 7. Concrete preliminary experiments (cheapest first)

Reuse the standing [`healthbench-local-eval`](../experiments/healthbench-local-eval/)
harness (single vLLM server on one GPU; Qwen3-4B target + judge) — `generate.py` and
`grade.py` already do exactly the generate-then-grade-per-criterion loop we need; the new
pieces are a *footprint classifier* and a *paired-grading driver*.

- **E1 — Age locality at small scale (the kill-shot; days, no new infra).**
  1. **Select** ~20–30 `full`-split items that state a specific age *and* have ≥1
     plausibly age-sensitive criterion (filter on the parsed rubric index).
  2. **Predict the footprint**: an LLM pass (a footprint-classifier prompt modeled on
     [`classifier_prompt.md`](../experiments/data-grounded-healthbench/src/dependency/classifier_prompt.md),
     but keyed to *age* with `kept/moot/reweight/induced/urgency/answer_shift`) tags each
     criterion **before** any model is run.
  3. **Generate** a minimal age-edited variant `V′` (e.g. 30→70) per item (LLM rewrite of
     just the age + entailed phrasing; diff-checked to confirm it's a one-dimension edit).
  4. **V1/V2 (no clinical judgment needed):** with the **judge at temp 0**, grade one
     fixed answer under `V` and `V′`; compute the **off-target verdict-change rate** on
     predicted-kept criteria vs. the move rate on predicted-footprint criteria →
     **footprint precision/recall**. Also estimate the judge-noise floor (grade identical
     triples K times).
  5. **Adaptation (optional this round):** generate a *fresh* answer for `V` and for `V′`,
     grade each under its own footprint-mutated rubric, and look for whether the model
     adapts.
  - **Kill-shot logic** (mirrors the agenda's E2): if off-target ≫ noise floor, age is not
     a clean dimension *or* our footprint prediction is poor — learn that in week one. If
     off-target ≈ floor and footprint criteria move, the locality hypothesis holds and the
     whole program is greenlit cheaply.
  - *Metrics:* off-target verdict-change rate vs. floor; footprint precision/recall;
     per-axis sensitivity; (optional) per-model counterfactual-consistency rate.

- **E1b — Measured footprint via the sweep test (§4.1; the fix the pilot motivated).**
  The first n=2 pilot had the a-priori classifier predict 0/22 criteria sensitive — not
  trustworthy. So instead of one A→B edit, instantiate age at **K values**
  (e.g. {18, 30, 45, 60, 75}) with the same minimal edit per value, and grade a *fixed*
  answer (ideally a few diverse answers) under each, each point ×R repeats for the noise
  floor. Per criterion: **invariant across the whole sweep ⇒ bridge; flips at some value ⇒
  footprint** (record the flip point). Then **score the a-priori classifier against this
  measured footprint** (agreement, and the disagreement list for review). This makes
  dimension-(in)dependence an *observed* property, not a model's opinion, and is the
  primary detector the rest of the program should use. *Metrics:* per-criterion sweep
  change rate vs. floor; predicted-vs-measured agreement (precision/recall of the cheap
  classifier); flip-point distribution. *(Concretely: a `sweep.py` step generalizing
  `paired_grade.py` from one variant to K — the driver already grades a fixed answer under
  an edited conversation, so this is a loop over values plus an invariance aggregation.)*

- **E2 — Add D3 (severity) and D5 (comorbidity toggle)** on the same item set; D3 adds the
  monotonicity check V3 (sweep mild→severe, watch urgency criteria tighten monotonically).

- **E3 — D2 (mode of disclosure) on ~10 items**, building on the phase-2 PoC: render a
  stated fact as structured data with the fact held constant; show the management bridge is
  invariant while only ask→interpret criteria move (the clean N1 control).

- **E4 — Scale + multi-model (resource-gated, same caveat as the agenda §5.2):** the
  consistency/equity profiles and any ranking claim need the HealthBench model suite and
  budget; run after E1 validates the mechanism.

A small, self-contained `experiments/counterfactual-mutation/` would host the footprint
classifier, the per-dimension editors, and the paired-grading driver, importing the
healthbench-local-eval grader rather than duplicating it.

---

## 8. Threats & honest limits

- **Locality is approximate, and that's the empirical question.** Real edits ripple
  (changing age can change the plausible differential, which changes several criteria).
  We don't assume locality — V1/V2 *measure* it per dimension and demote dimensions that
  fail. A dimension's value is its measured footprint precision/recall, reported, not
  assumed.
- **The judge is noisy and the grader must do new work.** Every V1/V2 statistic runs
  through the judge-noise floor (RubricEval-style ceilings; temp-0 or K-repeat
  estimation). D2/D5 ask the grader to verify a *value/contraindication* — validate the
  grader on those criteria specifically, as in benchmark-fit C6.
- **Bridge criteria can be subtly wrong even if their verdict doesn't flip** (a kept
  criterion may be *less appropriate* without flipping pass/fail). V4 delta-validation
  samples the bridge to guard this; we don't claim the bridge is perfect, only invariant
  within measured bounds.
- **Mutated footprint criteria are LLM-generated hypotheses** (the phase-2 caveat): they
  encode debatable clinical positions and are gated by V4, never shipped as gold.
- **Case-level variance & chain drift** (benchmark-fit §7) apply unchanged: pair within
  item so the ~82% case-level term differences out; bound provenance depth if we mutate
  mutated items.

---

## 9. Where this lives

Idea doc in `docs/` alongside its siblings; the work lands as a new
`experiments/counterfactual-mutation/` (E1 first), reusing the healthbench-local-eval
grader. Cross-refs: generalizes [`vision.md`](vision.md) §3; instantiates
[`benchmark-fit.md`](benchmark-fit.md) §5 (L2) and §6 (certification/bridge); shares the
quality yardstick of [`auto-rubric-generation.md`](auto-rubric-generation.md) §4. When E1
produces numbers, fold the footprint-precision/recall result back into benchmark-fit.md's
repair-ladder economics.
