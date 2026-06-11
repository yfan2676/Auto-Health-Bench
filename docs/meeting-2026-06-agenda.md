# Agenda — Direction B lit review results & proposal (2026-06)

> Background links for anyone who wants the details:
> [Direction-B lit review](lit-review/data-grounded-evaluation.md) ·
> [Direction-A lit review](lit-review/auto-rubric-generation.md) ·
> [framework proposal](benchmark-fit.md) ·
> [phase-2 PoC](../experiments/data-grounded-healthbench/reports/phase2-poc.md)

## 1. Goal, restated

Given a new product or model, we want to (a) quickly tell whether an existing benchmark
is a valid test for it, and (b) if not, generate a trustworthy one automatically, without
commissioning hundreds of experts. The deliverable is a research paper, but the fit-test
and mutation pipeline underneath should be reusable beyond it.

## 2. What the literature looks like

Both directions are now fully reviewed (~120 papers, citations checked against the
originals). The picture is three rings:

1. Evaluating health LLMs *with* user data is crowded. Feeding EHRs or wearables to
   models is well-trodden (PH-LLM, MedAgentBench, many others), so this angle is not a
   contribution on its own.
2. Auto-generating case-specific medical rubrics is crowding fast, with several papers in
   Jan–Feb 2026 alone. But in all of them the criteria adapt to the task or the
   guideline, not to what the data makes known.
3. Nobody studies how the rubric itself must change once the record is injected:
   criteria that reward asking become moot, new data-grounded criteria appear, urgency
   flips. I re-checked the nearest neighbors individually; none of them does this.

Our own measurements back this up: about 83% of HealthBench conversations contain no
patient data while 1,791 of 5,000 reward asking for it, and in the PoC the same original
rubric scores a data-blind answer 87% vs. a correct data-aware answer 25% (a 62-point
swing).

## 3. Why mutate HealthBench instead of building a new benchmark

The obvious alternative ("design a better benchmark on real data") answers a different
question. Four reasons to prefer mutation (full argument in the
[lit review §3.1](lit-review/data-grounded-evaluation.md#31-why-mutate-an-existing-benchmark-rather-than-build-a-new-one)):

- The finding we're after is a delta: how do the right answer, the rubric, and the model
  ranking change when data appears? That needs the original item as the baseline. A fresh
  benchmark has no "before"; it gives a level, never the mis-scoring.
- Power: roughly 82% of HealthBench label variance is case-level. Comparing across
  benchmarks drowns in that noise, while pairing within the same item cancels it.
- HealthBench carries 48,562 physician-written criteria from 262 physicians, and we
  currently have no physician access. Rebuilding from scratch means worse, unvalidated
  rubrics; mutating means experts only need to check the delta per item.
- Keeping the same items and model suite makes our numbers directly comparable to the
  published leaderboard ("model X is 3rd text-only, 6th with data").

A real-data benchmark isn't a competing idea. It's the later field study, once the
controlled instrument works.

## 4. Why this is worth being excited about

The mutation idea generalizes past HealthBench (written up in
[benchmark-fit.md](benchmark-fit.md)):

- It gives a fit test for benchmarks. Every benchmark quietly encodes assumptions about
  its operating conditions; HealthBench assumes the model only knows what the user typed.
  Inject the product's actual conditions and see whether scores and rankings hold. If
  they hold, the benchmark is fit for that product. If they shift, it isn't, and the
  drift tells you exactly which items and criteria are wrong — which is the repair list.
- Repair is much cheaper than rebuilding, because experts validate only the changed
  criteria. The cost of a trustworthy benchmark then scales with how far it is from a
  validated one, not with its size. That is what would make automatic benchmark
  generation affordable.
- It measures something no current benchmark reports: a data-use policy profile. Same
  case, four data states (none / missing field / noisy / clean), scored on whether the
  model asks, uses, or reconciles. Existing work either scores final answers with the
  data always present, or scores asking only as a means to accuracy; there is no setting
  anywhere in which asking is wrong. "Model M always-asks, model N always-trusts" would
  be a new kind of result.

One caution to keep: we are not claiming mutation can be made perfect, or that it covers
any benchmark. The claim is that fit is measurable and that repairs can be certified
within bounds (rank preservation plus delta expert validation). The
[claim ladder](benchmark-fit.md#8-the-claim-ladder--keeping-the-motivation-honest)
spells out what evidence licenses what.

## 5. Proposal and next steps

Proposal: position the work as the general framework (fit test + mutation +
certification), with HealthBench as the first worked demonstration. The early experiments
are identical either way; this mostly affects how we write it up.

Order of work, cheapest first:

1. Kill-shot: replicate the drift on ~50–100 classifier-flagged items. The PoC is n=2
   and the cases were hand-picked, so if the drift doesn't replicate at scale the
   motivation collapses — better to find that out right away.
2. If it replicates: full drift map plus ranking impact (Kendall τ with noisy-judge
   significance) over the model suite.
3. The policy profile: the four-data-state sweep on the same cases.
4. Stretch: a small transfer (~20 items) to a second benchmark — HealthBench Professional
   is the cheapest option — to show this is an operator, not a HealthBench patch.

Expected outputs: a headline number ("X% of HealthBench verdicts flip once data is
present"), the per-model policy profile, and a repair-vs-rebuild cost comparison.

## 6. Discussion

1. Framework positioning vs. "a new data-grounded benchmark": the right call for the
   paper?
2. Kill-shot threshold: what drift magnitude or flip rate counts as motivation confirmed,
   and what result would make us stop?
3. Validation ordering: proxy ensemble now, physicians later. Acceptable? When can
   clinicians realistically be looped in?
4. Transfer target: HealthBench Professional, or a non-health rubric benchmark?
5. Scope and venue for the write-up.
