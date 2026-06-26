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

The approach rests on two claims. We do not try to settle them by argument here; the
evaluation we propose is what actually tests them. The goal here is just to show they are
reasonable enough to be worth testing.

**Claim 1: a small, controlled change to a case touches only a small, predictable part of
the rubric, and we can measure which part.** Most criteria describe general good care
(show empathy, ask about the symptom, explain clearly) and do not depend on the one
variable we change, such as the patient's age; only a handful are tied to it, like
age-specific screening or dosing. We do not have to take this on faith: grade one fixed
answer against the rubric before and after the change, and any criterion whose verdict
stays the same was, by direct evidence, unaffected. So "the change is local" becomes a
counted result, and a change that moves too many criteria is simply discarded as a poor
candidate.

**Claim 2: today's models can perform these changes reliably enough to be useful.**
Specifying what a good answer looks like, offline, for cases we choose is far easier than
the live task a deployed model faces, so what we ask of the model is a small, constrained
edit, not open-ended generation. We also inherit the expert rubric verbatim and ask the
model only to edit the few criteria the change touches, which is small enough to check
automatically and to put in front of an expert. Recent work already auto-generates medical
rubrics at close to physician quality, so the open question is not whether a model can
write useful criteria but how to validate what it writes, which is what the evaluation
does.

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

### What do we compare against?

Several of the approaches above assume a trusted reference rubric, which is awkward for a
mutation: by construction, the modified setting has no pre-existing expert rubric. There is
no single gold reference. What we compare against depends on which part of the rubric we are
checking.

- **The unchanged part is its own reference.** A mutation rewrites only a small set of
  criteria and inherits the rest of the expert rubric word-for-word. For that inherited
  majority, the original expert rubric *is* the reference: the test is that those criteria
  keep their verdicts, and reproduce the same model ranking, after the edit as before. That
  covers most of the rubric and needs no new expert work.

- **The changed part has no existing reference, by design.** For the few criteria the
  mutation rewrites, there is no prior expert rubric to compare to, so we do not pretend
  there is one. Instead we have an expert review just that small delta, and we require it to
  pass behavioral sanity checks, for example that a more severe case tightens the urgency
  criteria, or that better data raises a competent model's score. These stand in for a gold
  reference where none can exist.

- **Where a real reference does exist, use it.** Existing benchmarks already contain natural
  pairs of cases that differ along a dimension we mutate (a younger and an older patient, a
  milder and a more severe presentation), each with its own physician rubric. We can mutate
  one case toward the other and compare our result against the actual expert rubric for that
  target. This gives a genuine gold comparison for the dimensions where such pairs can be
  found.

- **A baseline comparison needs no gold at all.** "Are our mutations better than a simpler
  method's?" is a relative judgment: produce the modified rubric two ways (our method versus
  an off-the-shelf baseline) and have experts say which they prefer. This measures whether we
  beat the obvious alternative, with no reference rubric required.

The cleanest case is changing only how a fact is presented (the same hypertension stated in
prose, then shown as a blood-pressure reading). Because the underlying clinical facts do not
change, almost the entire expert rubric still applies as the reference, and only the "stop
asking for it" and "read the value correctly" criteria are expected to move.

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

## Experiments

Each experiment below is designed so that every possible outcome changes what we believe or
what we would do next. As a rule of thumb, if an experiment could only confirm something we
already assume, or if neither result would change a decision, we treat it as unnecessary and
do not run it. We are most interested in the data setting, so the questions are framed there.

### What we have run

**1. How much of the benchmark already supplies patient data.** This grounds the diagnosis
step (is the benchmark a fit for a data-equipped product?). The question: in the existing
benchmark, how often is the patient's own data already present, versus how often does a
criterion reward the model for asking for data a record could supply? If most cases already
include the data and rarely reward asking, a text-only benchmark already resembles a
data-present product and little repair is needed. If most cases are data-blind yet still
reward asking, there is a large mismatch worth fixing. Result: about one in six
conversations contain the patient's own structured data, almost none contain wearable data,
and roughly 1,791 of 5,000 cases reward asking for information a record could hold. The
mismatch is large, which is what justifies working on the data dimension at all; a small
mismatch would have told us to drop it.

**2. Does the original rubric still score correctly once the answer uses the record?** This
grounds Claim 1 and the fit test in the data dimension. The question: when we add the
patient's record and the model correctly uses it, does the original rubric still reward that
answer? If the data-aware answer scores at least as well as a data-blind one, the benchmark
transfers to the data setting unchanged. If it scores lower, the benchmark is penalizing
correct behavior and needs repair. Result (a 30-case proof of concept): under the original
rubric the data-aware answer averaged 42% against the data-blind answer's 59%, the original
rubric lost points for using the record in 19 of 30 cases (one sharp case swung 62 points),
and a data-conditioned rubric restored the data-aware answer to 71%. The same run also
caught a model that had the data on file and still gave generic advice, a failure the
text-only benchmark could not see. The opposite result (no score drop) would have told us
the data axis does not matter for this benchmark. Caveat: small sample, a model grader
standing in for physicians, and the mutated rubric is a hypothesis that still needs review.

**3. Where does a single-variable edit actually move the rubric?** This grounds Claim 1
(a controlled change touches a small, predictable part, and we can measure which part). The
question: when we change exactly one variable (age, severity, an added condition, pregnancy,
how a fact is disclosed, or sex) and hold the rest fixed, do the graded outcomes move only
where that variable should matter, and by how much above the model's own answer-to-answer
noise? We ran this across six variables on a 27B model with a significance test. Three kinds
of outcome are all informative: a real change concentrated where expected (the variable is
local, and a model that fails to move there has a gap), no change above noise (a true "no
effect," which is what we want for a protected attribute like sex), or change scattered
everywhere (the variable is not local, so we should not cheaply mutate along it). Result:
severity and age produced real, significant score drops (about 17 and 11 points); changing
how a fact is disclosed (prose versus a number) moved behavior without a consistent
direction, exposing a numeracy gap; sex, the control, showed no effect, as it should; and
the change concentrated in completeness and accuracy while communication stayed the most
stable, matching the prediction that the general-care part of the rubric is what does not
move.

### What we propose to run

**4. Rank preservation in the data dimension (the headline test).** This grounds the
diagnosis step and the "preserving the model ranking" row of the evaluation. Run a suite of
models twice on the same cases: once graded by the original text-only rubric, once by the
data-conditioned rubric with the record present. Then compare the two model rankings. There
are two outcomes, and both decide something real:

- *The ranking is preserved.* The data-present rubric orders the models the same way the
  original does. This means a model's text-only score already predicts how it would stand in
  the data setting, so for the purpose of choosing a model the existing benchmark is fit to
  use as-is, and the data repair changes absolute scores and reveals behaviors but not the
  leaderboard. Useful: it tells a product team they can trust the existing benchmark for
  model selection, and it bounds our own claim honestly.
- *The ranking changes.* A model that looks best on the text-only benchmark is not the best
  once the record is present. This means the existing benchmark gives the wrong leaderboard
  for a data-equipped product, which is the strongest justification for repairing it, and
  the reordering points to which models and criteria drive the change. Useful: it tells the
  same product team that picking a model on the existing benchmark would be a mistake.

Either way the result changes a real decision (trust the existing leaderboard, or repair
before trusting it), which is why the experiment is worth running. One guard: a ranking
change reads as "the benchmark is unfit" only after the check below passes. On the inherited,
unchanged criteria the mutated rubric must reproduce the original ranking; if even those
shift, the problem is our pipeline, not the benchmark.

**5. The self-certifying check: do the unchanged criteria really stay unchanged?** This
grounds Claim 1's "we can measure which part" and the "unchanged part is its own reference"
argument. Hold one model answer fixed and grade it against each criterion before and after
the edit, changing only the case. The criteria we predicted unchanged should keep the same
verdict, at the rate the grader flips on identical inputs (its noise floor). If they sit at
the floor, the inherited part is certified automatically with no expert, and only the changed
criteria need review. If they move well above the floor, the edit leaks further than
predicted and we demote that variable. (Our six-dimension run measured a related fresh-answer
version of this; the fixed-answer version is the cleaner certificate and is the next step.)

**6. Repair versus rebuild (the economic claim).** This grounds the utility argument that the
cost of a trustworthy benchmark scales with the size of the change, not the size of the
benchmark. On the cases that drift, build the data-present rubric two ways: mutate the few
affected criteria, or generate a fresh rubric from scratch with an off-the-shelf method.
Compare them on agreement with the trusted ranking over the unchanged criteria and on how
many criteria a human must review. If mutation matches the from-scratch quality at a fraction
of the expert review, the repair-not-rebuild thesis holds. If from-scratch is just as cheap
or clearly better, the central economic claim is wrong and we would switch to generation.
Either result settles whether the method is worth using.

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
