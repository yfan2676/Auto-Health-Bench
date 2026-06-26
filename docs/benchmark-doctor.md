# Benchmark Doctor

A "benchmark of benchmarks" that checks whether an existing test is a good fit for a
given product or model. When it is not, it repairs the test with small, controlled
changes that keep most of the original expert quality.

---

## The idea in one paragraph

Good health-AI benchmarks are expensive. A benchmark like HealthBench took hundreds of
physicians and tens of thousands of hand-written grading criteria to build. When a
company wants to test a new product or model, they face two questions: is there already
a benchmark that validly tests *this* product, and if not, do they have to build a new
one from scratch? Building from scratch throws away all the expert work that went into
the benchmarks we already have. Our proposal is to treat this like a doctor would:
first **diagnose** whether an existing benchmark fits the product, and if it does not,
**treat** it with the smallest change that makes it fit, rather than replacing the
whole thing. We call this the **Benchmark Doctor**.

---

## Why this matters

A benchmark is only meaningful if a high score on it actually predicts that the product
will behave well in the real world. The problem is that every benchmark quietly assumes
a particular setting: who the user is, what the model is allowed to know, how
information arrives, how urgent things are. These assumptions are rarely written down,
but they decide what counts as a "right answer."

When the product's real setting differs from the benchmark's assumed setting, the
benchmark can score the wrong thing; sometimes it even rewards behavior that would be
wrong in deployment. A concrete example from our own work: HealthBench was written
assuming the model only knows what the user typed, so many of its criteria reward the
model for *asking* the patient for information. But a real wearable or connected-health
assistant already has the patient's record. In that setting, asking for data the system
already has is not good behavior, yet the original benchmark still gives points for it.
On a small proof-of-concept, the original grading scored a correct, data-aware answer
*lower* than a data-blind one. The benchmark is not broken; it is simply being used
outside the setting it was written for.

So the practical need is: a fast way to tell whether a benchmark fits your product, and
a cheap way to fix it when it does not.

---

## What is missing today

The field already has useful pieces, but none of them solves this directly:

- **Benchmark quality checks** ask whether a benchmark is internally sound, never whether
  it is sound *for this particular product*. A benchmark can be excellent and still be the
  wrong test for you.
- **Automatic benchmark generators** build new benchmarks from scratch. That discards
  the expert validation already baked into existing benchmarks, and it pays the full
  cost of validating a brand-new test.
- **There is no agreed standard** for when an automatically modified benchmark is good
  enough to trust. Recent work has shown that "a model can generate grading criteria"
  does not mean "those criteria actually work."

The Benchmark Doctor fills the gap between "check if it's good in general" and "build a
whole new one": check if it's good *for you*, and if not, make the smallest repair.

---

## The core bet, and why it is reasonable

The whole approach rests on two claims. Both sound plausible, but they deserve a clear
argument, because everything else depends on them.

### Claim 1: a small, controlled change to a case touches only a small, predictable part of the rubric, and we can measure exactly which part.

A rubric is a list of mostly separate grading criteria. Many of them describe general
good-care behavior: show empathy, ask about the symptom, explain clearly, give safety
advice. These do not depend on the patient's exact age, or on whether a fact was typed
in prose or shown as a lab value. Only a handful of criteria are tied to the thing we
changed, such as age-specific screening or drug dosing. So before running
anything, we already expect that changing one variable moves only a few criteria.

The important point is that we do **not** have to take this on faith. We can measure it,
cheaply, and without any human expert, using a simple before-and-after check:

1. Take one fixed model answer.
2. Grade that same answer against the rubric on the original case, then on the changed
   case.
3. Any criterion whose pass/fail verdict stays the same was, by direct evidence,
   unaffected by the change. Any criterion whose verdict flips is one the change actually
   touched.

This turns "I believe the change is local" into a counted result: how many criteria
actually moved. If a change moves only a few criteria, it is local; if it moves many, it
is not, and we simply discard that kind of change as a poor candidate. The method polices
itself.

We make this more reliable in two ways. First, instead of a single before-and-after, we
sweep the variable across several values (for example, ages 18, 30, 45, 60, 75) and
watch which criteria stay constant across the whole range. A criterion that never moves
across a wide, realistic range is very likely truly independent of that variable, and our
confidence grows the wider we sweep. Second, we separate real movement from grader noise
by grading the same item several times (or at a fixed, deterministic setting) to learn
how often the grader flips on its own; we then only count movement that clearly exceeds
that noise.

This is a well-established testing idea, applied one grading criterion at a time: assert
that a controlled change should not affect certain outputs, then hunt for violations. The
payoff is large: the criteria we do *not* change certify themselves by staying the same,
so we only ever need expert attention on the small set that did change.

### Claim 2: today's models can perform these counterfactual changes reliably enough to be useful.

A "counterfactual change" here means producing a realistic, internally consistent version
of a case that differs in exactly one thing (the same complaint for an older patient, the
same fact shown as a data value instead of a sentence, or the same case with one added
condition), and then editing the few rubric criteria that this affects.

There are three reasons to believe current models are up to this.

**The task we are asking the model to do is much easier than the task we are testing.**
A deployed health model has to take arbitrary, messy, real patient data and produce the
ideal answer, live, for every input. By contrast, our pipeline only has to *describe what
a good answer looks like*, offline, for cases we choose. Writing a controlled variant of
an already-validated case, and adjusting a handful of criteria, is a small, constrained
rewrite. This gap, where specifying the right answer is far easier than producing it, is
the reason the evaluation can be automated even though the model under test cannot be.

**We never trust the model to redo the hard part.** The large, expert-written portion of
the rubric is inherited word-for-word; no model is asked to re-derive it. The model is
only asked to (a) make a clean one-variable edit to the case and (b) rewrite the small set
of criteria that the change affects. The first is easy to verify automatically (a simple
diff confirms only the intended variable changed). The second produces the only genuinely
new clinical content, and it is small enough for a human expert to review.

**Every step is checkable, so errors surface instead of silently corrupting the
benchmark.** We cross-check the model's claim about which criteria *should* change against
the measured before-and-after result from Claim 1. When the model's prediction and the
measurement agree, we have high confidence; when they disagree, that case goes to a review
queue. We use more than one signal rather than trusting a single model call.

The recent literature supports the feasibility directly: as of early 2026, several groups
have automatically generated medical grading rubrics and validated them on HealthBench,
with some reporting quality on par with physician-written rubrics. So "can a model produce
useful clinical criteria at all" is largely settled: yes. The open problem is how to
*validate* the result, which is exactly what the measurement in Claim 1 is for.

The honest version of Claim 2 is therefore not "the model's changes are perfect." It is:
the changes do not need to be perfect, they need to be *checkable*; the design makes each
step checkable, keeps the genuinely new content small, and inherits the rest from experts.

---

## The proposed pipeline (using the data setting as the example)

The Benchmark Doctor can adjust several different aspects of a case: the patient's age,
the severity of symptoms, an added condition or medication, whether the patient might be
pregnant, or how a fact is presented. The clearest worked example is the **data setting**:
moving a text-only benchmark into the setting of a product that already holds the patient's
record. The user picks the aspect they care about, and the workflow runs like this:

1. **Start from a realistic question.** Take a real member-style question from HealthBench
   (or a similar benchmark), a genuine case a user might bring to a health assistant.

2. **Choose a patient profile that adds a realistic complication.** Decide what kind of
   patient would make this case more clinically interesting, for instance a profile
   whose history changes the safe course of action. The goal is a realistic complication,
   not an arbitrary one.

3. **Get matching data for that profile.** Source patient data that fits the profile,
   either from a real dataset (a clinical trial or cohort) or generated synthetically to
   the profile. (The project currently uses synthetic generation, because it avoids data-
   governance constraints and keeps the result openly reproducible; real cohorts and trial
   data are an option for later.)

4. **Update the rubric for the new complication.** Keep the large, untouched part of the
   expert rubric as-is. Change only the criteria the new data affects: drop criteria that
   reward asking for information the record now supplies, add criteria that reward correctly
   reading and using that information, and adjust urgency where the data changes it.

5. **Test models on the new rubric.** Run the model suite against the updated case and
   rubric, and compare against the original to see where, and for which models, the verdict
   changes.

Crucially, **every step gets its own check** so we can show it actually works:

- Step 1–3: the generated case and data are checked for being a clean, single-variable,
  internally consistent change.
- Step 4: the before-and-after measurement from Claim 1 confirms that the untouched
  criteria really do stay put, and a small expert review covers only the changed criteria.
- Step 5: we confirm the result behaves sensibly. For example, giving a competent model
  better data should raise its score, not lower it; if it does not, the test, not the
  model, is suspect.

---

## Why the method is useful

- **It reuses expensive expert work instead of throwing it away.** The cost of trusting a
  modified benchmark scales with the *size of the change*, not the size of the benchmark.
  Most of the rubric is inherited; experts review only the small edited part.

- **It turns a yes/no question into an actionable answer.** "Does my product need a new
  benchmark?" stops being a guess. The answer is either "the existing one fits," "it needs
  a small repair (here is the repair, and here is what it costs to check)," or "this is
  genuinely new territory and a new benchmark is justified."

- **It produces minimal-pair test cases.** Because each new case differs from a known good
  case in exactly one way, comparisons are far cleaner than comparing two unrelated cases.
  Differences in the score can be attributed to the one thing we changed.

- **It can reveal model properties no current leaderboard reports.** For example: does a
  model correctly switch from *asking* for information to *using* it when the record is
  present? Does its general care quality stay steady when only the patient's age changes,
  or does it quietly get worse? A silent drop would be a fairness signal that is hard to
  argue with, because the untouched criteria are supposed to be unaffected by age.

---

## How we will judge whether a modification is good

This is the least settled part: **this is an emerging area, and there is no single
agreed-upon metric for the quality of a rubric modification.** Recent work uses several
different yardsticks, each measuring something slightly different. Our plan is to lead with
the one that best fits "did the modification preserve quality," and to report several
rather than bet on one.

| Approach | What it checks | Status in the field |
|---|---|---|
| Expert rating of the result | Do clinicians judge the modified rubric/criteria as correct? | The gold standard, but expensive, and limited by the fact that experts themselves disagree a lot (so there is a ceiling on how much agreement is even achievable). |
| Agreement with an expert-made rubric | Do scores from the modified rubric track scores from the human reference? | Common; usually done as per-item correlation. Works only where a trusted reference exists. |
| Preserving the model ranking | Does the modified rubric rank a set of models the same way the trusted rubric does? | Under-used, and a good fit for "did we keep the quality." This is the yardstick we lean on; it needs care, because rankings can be fragile, so it must be reported with significance tests, not as a single number. |
| Direct comparison of rubrics | Side-by-side, is the generated rubric as valid as a human-written one? | A recent benchmark does exactly this and finds models still struggle to write fully valid criteria on their own, which is why we modify rather than generate from scratch. |
| Use as a training reward | Does training a model with the rubric as the reward signal improve it? | The most common validation in recent work. Strong signal, but it measures usefulness for *training*, not correctness of the *evaluation*, and it is expensive to run. |
| Head-to-head against a baseline method | Do experts prefer our modifications over those from a simpler method? | Acceptable and done in the field (clinician-refinement studies). The strongest "is it actually better" evidence, and the most costly. |

A few honest caveats that apply to all of these:

- The automatic grader is itself imperfect, so every comparison has to account for grader
  noise rather than assume the grader is right.
- Most of the disagreement on health answers comes from the *case*, not from the rubric, so
  a better rubric can only close part of the gap. Success should be framed as reproducing
  the expert ranking or score pattern, not as eliminating disagreement.
- "It generated something" is not "it works." That is the entire reason we measure, rather
  than assume, that a modification preserved quality.

The most defensible position, given all this, is: we do not claim our modifications are
perfect. We claim you can *tell how good they are and what it costs to check*, and that is
exactly the position the evidence supports.

---

## Honest limits

- A change is only as local as it actually is; some changes ripple further than expected.
  We measure this per change and drop the ones that ripple too much, rather than assuming.
- The "build it once for any benchmark" version is a long-term goal. The data setting works
  for health because realistic patient data can be generated; other domains would need their
  own way to produce realistic context.
- Modified criteria are model-written hypotheses about good care. They are reviewed by an
  expert before being trusted, never shipped as ground truth on the model's say-so.

---

## Companion documents

Related documents, in more depth:

- `benchmark-fit.md`: the full framework, covering fit as a measurable quantity, repair as
  a graduated ladder, and a certification standard.
- `counterfactual-mutation.md`: the operator behind the small controlled changes, and how
  the locality claim is made to validate itself.
- `vision.md`: the data-grounded evaluation track in depth.
- `auto-rubric-generation.md`: what makes a rubric good and how to generate one.
- `lit-review/`: the underlying literature, including the work cited in the evaluation
  section above.
