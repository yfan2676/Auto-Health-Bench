# Meeting agenda — Direction B review → benchmark mutation proposal (2026-06)

> 10–15 min walk-through, then open discussion. Deep dives are linked, not inlined:
> [Direction-B lit review](lit-review/data-grounded-evaluation.md) ·
> [Direction-A lit review](lit-review/auto-rubric-generation.md) ·
> [framework proposal](benchmark-fit.md) ·
> [phase-2 PoC](../experiments/data-grounded-healthbench/reports/phase2-poc.md)

## 1. The goal (1 min)

Given a new product or model: **(a)** quickly tell whether an existing benchmark is a
*valid* test for it, and **(b)** if not, generate a trustworthy one automatically —
without commissioning hundreds of experts. Deliverable: a research paper, plus evaluation
machinery designed to outlive it (the fit-test + mutation pipeline is the reusable part).

## 2. Lit-review landscape — three concentric rings (3 min)

Both directions now fully reviewed (~120 papers, citations verified). Outer to inner:

1. **"Evaluate health LLMs *with* user data" — crowded.** Feeding EHRs / wearables to
   models is well-trodden (representatives: Google's PH-LLM, Stanford's MedAgentBench).
   Not a contribution on its own.
2. **"Auto-generate case-specific medical rubrics" — crowding fast.** Several papers in
   Jan–Feb 2026 alone. Criteria adapt to the *task or guideline*, though — not to what
   the data makes known.
3. **"Mutate the rubric *because data was injected*" — open.** No work studies how the
   scoring criteria themselves must change when the record arrives: criteria rewarding
   *asking* become moot, new data-grounded criteria appear, urgency flips. The nearest
   neighbors were individually re-verified — none does this.

Supporting evidence from our own measurements: ~83% of HealthBench conversations contain
no patient data while 1,791/5,000 *reward asking for it*; in the PoC the same original
rubric scores a data-blind answer 87% vs. a correct data-aware answer 25% (**−62pp**).

## 3. Why mutate HealthBench rather than build a new benchmark (3 min)

The obvious alternative — "just design a better benchmark on real data" — answers a
different question. Four reasons mutation is the right design
([full argument](lit-review/data-grounded-evaluation.md#31-why-mutate-an-existing-benchmark-rather-than-build-a-new-one)):

- **The finding is a delta.** "How do the right answer, rubric, and ranking change when
  data appears?" requires the original item as the counterfactual baseline. A fresh
  benchmark has no *before* — it gives a level, never the mis-scoring.
- **Statistical power.** ~82% of HealthBench label variance is case-level. A
  between-benchmark comparison drowns in that noise; within-item pairing differences it
  out. The paired design is close to *necessary*, not just convenient.
- **Inherit the expert gold.** HealthBench = 48,562 physician-written criteria from 262
  physicians. We have no physician access right now — rebuilding means *worse,
  unvalidated* rubrics. Mutation re-validates only the **delta** per item.
- **Comparability.** Same items + same model suite ⇒ results align directly with the
  published leaderboard ("model X is 3rd text-only, 6th with data").

A real-data benchmark isn't the rival — it's **downstream** (validate the instrument
first, field-study later).

## 4. Why this is enticing — from patch to framework (3 min)

Rubric mutation generalizes ([proposal doc](benchmark-fit.md)):

- **A fit test for benchmarks.** Every benchmark silently encodes operating assumptions
  (HealthBench: "the model only knows what the user typed"). Inject the product's real
  conditions and check whether scores/rankings are **invariant**: invariant → the
  benchmark is fit; shifted → unfit, *and the drift localizes exactly which items and
  criteria are wrong* — a repair work-list, not just a verdict.
- **Repair beats rebuild on cost.** Experts validate only changed criteria ⇒ the cost of
  a trustworthy benchmark scales with its *edit distance* from a validated one, not its
  size. This is what makes "automatically produce a new benchmark" affordable at all.
- **A model property nobody reports.** The **data-use policy profile**: same case swept
  across four data states (none / missing field / noisy / clean), scoring whether the
  model *asks*, *uses*, or *reconciles* appropriately. Existing work either scores final
  answers with data always present, or scores asking only as a means to accuracy — **no
  existing scoring function ever makes asking *wrong***. "Model M always-asks, model N
  always-trusts" is a deliverable no current benchmark can produce.

Claims discipline: we do *not* claim mutation can be made perfect or that it covers any
benchmark — we claim fit is *measurable* and repair is *certified within bounds* (rank
preservation + delta expert validation). See the
[claim ladder](benchmark-fit.md#8-the-claim-ladder--keeping-the-motivation-honest).

## 5. Proposal + concrete next steps (3 min)

**Proposed positioning:** the general framework (fit test + mutation + certification),
with HealthBench as the first worked demonstration. Early experiments are identical
either way; positioning mainly affects how we write it up.

Sequenced cheap-first:

1. **Kill-shot (first ~month):** replicate drift at scale on ~50–100
   classifier-flagged items. The PoC is n=2 and the cases were chosen to be sharp — if
   drift doesn't replicate, the motivation deflates and we want to know immediately.
2. **Drift map + ranking impact:** full Δscore / Δrank (Kendall τ, noisy-judge
   significance) over the model suite.
3. **Policy profile:** the four-data-state sweep on the same cases — the
   "new model property" deliverable.
4. **Stretch — transfer demo:** ~20 items on a second benchmark (HealthBench
   Professional is cheapest) to show this is an operator, not a HealthBench patch.

**Expected outputs:** a headline number ("X% of HealthBench verdicts flip once data is
present"), the per-model policy profile, and a repair-vs-rebuild cost comparison.

## 6. Discussion (open)

1. Is the **framework positioning** (vs. "a new data-grounded benchmark") the right
   call for the paper?
2. **Kill-shot threshold:** what drift magnitude / flip rate would we consider
   "motivation confirmed"? What result would make us stop?
3. **Validation:** proxy (multi-model ensemble) now, physician round later — is the
   ordering acceptable, and when realistically can clinicians be looped in?
4. **Transfer target:** HealthBench Professional vs. a non-health rubric benchmark —
   which makes the generality claim credible enough?
5. **Timeline/venue:** what scope fits the internship window, and where do we want to
   submit?
