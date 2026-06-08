# Automatic Rubric Generation

> **Scope.** Idea doc for **Direction A** of the [Auto-Health-Bench](../README.md)
> project — *what makes a good rubric, and can we generate good ones automatically?*
> Runs in parallel to **Direction B** (data-grounded evaluation, [`vision.md`](vision.md))
> and intersects it at *data-conditioned rubric generation* (§5).
>
> **Status:** early — seeded from the 2026-06-08 collaborator meeting. No experiment yet;
> the first one is scoped in §4.

## 1. Why

Health-LLM answers are graded against **rubrics**: physician-written checklists of what a
good answer must contain, each item carrying points. Rubrics are the load-bearing artifact
of the whole field — yet they are expensive, require clinical expertise, are inconsistent
across experts, and don't scale to new tasks or products. If we can **auto-generate
rubrics that are as good as hand-written ones**, we lower the cost of trustworthy
evaluation and make on-demand benchmarks possible. This feeds the project's north-star
question: *given a product or use case, is it already covered by an existing benchmark, or
does it need a new one — and can we generate that new benchmark automatically?*

## 2. What makes a rubric "good"? (making the target measurable)

Before we can *generate* rubrics, we need a *measurable* notion of rubric quality.
Candidate properties:

- **Coverage** — items span what a good answer should address (no major gaps).
- **Discriminativeness** — items actually separate better answers from worse ones (not
  trivially all-pass / all-fail).
- **Weight calibration** — points reflect the relative importance of items.
- **Clinical correctness** — items are medically right (the part most needing validation).
- **Non-redundancy** — items don't double-count the same requirement.
- **Rank preservation** — grading a panel of model answers with the rubric reproduces the
  ranking a trusted reference rubric (or expert) would give. ← the property we can
  operationalize first (§4).

### Open question — relative scoring between items (meeting, 2026-06-08)

How should we set the **discrete / relative scores** between rubric items? HealthBench
items carry integer points, but the "right" weights are themselves contested — **experts
disagree with each other** about what matters most. So the target is not a single gold
weighting; it is a *distribution* of defensible weightings. Threads to study:

- Can we **learn** item weights from expert *answer rankings* rather than asking experts
  to assign points directly?
- How much does the model **ranking** (the thing we ultimately care about) depend on the
  exact weights vs. just the *set* of items? If rankings are robust to weight noise, exact
  weights matter less — a useful result for automation.
- Can we report a rubric score as a **range** over expert-plausible weightings instead of
  a single point estimate, so disagreement is represented rather than hidden?

## 3. Generating tasks at HealthBench quality (data-agnostic, for now)

A parallel sub-thread (meeting, 2026-06-08): can we **generate more tasks like
HealthBench's — at the same quality — without yet adding user data?** Staged:

1. **Augment / modify existing HealthBench items effectively** — can we edit or extend an
   item *and its rubric* without degrading quality? (This step is shared with Direction B,
   which augments items with patient data.)
2. **Generate genuinely new tasks** — conversations + rubrics that match HealthBench's
   quality bar, judged by the metrics in §2.

Holding data *out* at first isolates "can we generate good tasks/rubrics at all?" from
"does the data change the right answer?" (Direction B). It also gives a clean
quality bar to certify before the harder data-grounded version.

## 4. First experiment — rank-preserving rubric generation (the actionable next step)

A clear, measurable goal to start Direction A — and one that needs **no physician access**
to begin, since the original HealthBench rubrics serve as the reference:

1. **Define a rubric quality metric**, anchored on **rank preservation** (§2).
2. **Hold out** a portion of HealthBench (items + their physician rubrics).
3. **Auto-generate rubrics** for the held-out items *from the conversation alone* — without
   peeking at the original rubric.
4. **Compare** generated vs. original: grade a fixed panel of model answers under each
   rubric and check that the **generated rubric preserves the model ranking** the original
   rubric produces (e.g. Kendall's τ / Spearman over per-model scores), plus item-level
   overlap and the §2 properties.

**Success criterion:** our automated rubrics **reproduce the original rubrics' model
ranking** on held-out items. Concrete, measurable, physician-free to start; physician
validation slots in later, exactly as in Direction B. This is the first candidate to
become `experiments/<rubric-generation>/`.

## 5. Where A meets B

Once we can generate a good rubric for a *text-only* item (§4), the natural extension is
generating a **data-conditioned** rubric — one that adapts to an injected patient record.
That is the **A∩B** intersection the project is built around; Direction B's current
experiment already prototypes it via automatic rubric **mutation** (see
[`vision.md`](vision.md) §8 and
[`../experiments/data-grounded-healthbench/reports/phase2-poc.md`](../experiments/data-grounded-healthbench/reports/phase2-poc.md)).
The §4 rank-preservation metric is exactly the yardstick we will reuse to judge whether a
*data-conditioned* generated rubric is any good.

## Open questions parked from the meeting (2026-06-08)

- Relative / discrete scoring between rubric items under expert disagreement (§2).
- Does ranking robustness make exact item weights less important than the item *set*?
- How do we certify "HealthBench quality" for a *generated* task (§3)?
- The product-fit north-star: turning §4's machinery into a quick "fits an existing
  benchmark vs. needs a new one" test for a given product or use case.
