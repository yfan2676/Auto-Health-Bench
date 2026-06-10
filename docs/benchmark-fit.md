# Benchmark Fit & On-Demand Benchmark Generation

> **Scope.** Methodological proposal for the project's **north-star question** (parked in
> [`auto-rubric-generation.md`](auto-rubric-generation.md) §Open-questions): *given a new
> product or model, can we quickly validate whether an existing benchmark is fit to test
> it — and if not, quickly and automatically generate a new one?* Directions A
> (rubric generation, [`auto-rubric-generation.md`](auto-rubric-generation.md)) and B
> (data-grounded evaluation, [`vision.md`](vision.md)) are *instances* of the machinery
> proposed here; this doc states the general method they instantiate.
>
> **Status:** exploration-stage proposal (2026-06-10). No experiment yet; first
> experiments scoped in §9; claim discipline in §8. Literature grounding:
> [`lit-review/auto-rubric-generation.md`](lit-review/auto-rubric-generation.md) and
> [`lit-review/data-grounded-evaluation.md`](lit-review/data-grounded-evaluation.md).

---

## 1. The problem, stated operationally

A company ships a new product (say, a wearable health assistant) or a new model. Two
questions must be answered *before* any leaderboard number means anything:

- **Q1 — Fit.** Is some existing benchmark a valid test for *this* product/model? Not
  "is it on-topic," but: does a score on it predict quality in *this* deployment?
- **Q2 — Generation.** If not, how do we get a valid benchmark *quickly and
  automatically* — without commissioning 262 physicians for a year?

Today both are answered by expert judgment and vibes. The field has pieces — automatic
benchmark *construction* (AutoBencher [2407.08351](https://arxiv.org/abs/2407.08351),
BenchAgents [2410.22584](https://arxiv.org/abs/2410.22584), ArenaBencher
[2510.08569](https://arxiv.org/abs/2510.08569)), benchmark *quality* audits (construct
validity, [2511.04703](https://arxiv.org/abs/2511.04703),
[2503.10694](https://arxiv.org/abs/2503.10694)), contamination-free *refresh*
(LiveBench [2406.19314](https://arxiv.org/abs/2406.19314)) — but three gaps remain:

1. **Quality audits are product-agnostic.** Construct-validity checklists ask "is this
   benchmark internally sound?", never "is it sound *for this product's operating
   conditions*?" A benchmark can be excellent and still wrong for you — HealthBench is
   excellent, and our Phase-2 PoC shows it actively penalizes correct behavior in the
   data-present regime ([phase2-poc.md](../experiments/data-grounded-healthbench/reports/phase2-poc.md):
   −62pp on the sharp case).
2. **Generators build from scratch.** AutoBencher/BenchAgents synthesize new benchmarks
   wholesale, discarding the expert validation embedded in existing ones, and validate by
   desiderata (difficulty, novelty, separability) — not by whether the new benchmark
   *agrees with a trusted reference where they overlap*.
3. **There is no certification standard.** Nothing tells you when an auto-generated
   benchmark is *good enough to trust* — the skeptic result ("Are Checklists Really
   Useful?", [2508.15218](https://arxiv.org/abs/2508.15218)) shows "it generates" ≠ "it
   works."

The proposal: make **fit** a measured quantity (§3–4), make **generation** a *graduated
repair* of the nearest validated benchmark rather than a from-scratch build (§5), and
make **trust** a certification gate that chains back to expert-validated roots (§6).

---

## 2. Formal objects (minimal, but load-bearing)

- A **benchmark** is a triple **B = (T, S, Θ)**: a task distribution *T* (items), a
  scoring function *S* (rubrics + judge + aggregation), and — crucially — **Θ, the
  latent regime assumptions** baked into both: what the model is assumed to know (data
  availability), how context arrives (interface), who the user is, turn structure,
  modality, time period. Θ is almost never written down; vision.md §1 calls it
  "load-bearing and invisible." HealthBench's Θ includes *"the model knows only what the
  user typed"* — and ~83% of its items are data-blind under that assumption
  ([user-data-prevalence.md](../experiments/data-grounded-healthbench/reports/user-data-prevalence.md)).
- A **product context** is **C = (P, θ\*, w)**: the input distribution *P* it will face,
  the deployment regime *θ\** (what data/interface/users it actually has), and risk
  weights *w* (which failures are costly).
- **Fit(B, C)** is then not a yes/no but a **vector of measurable mismatches** between
  (T, S, Θ) and (P, θ\*, w) — §3 — plus a **behavioral test** of whether the mismatches
  matter — §4.

This framing converts "is the benchmark appropriate?" from a judgment call into a
question with an experimental answer.

---

## 3. Novelty 1 — the Fit Report: four measured components

Each component is automatable with machinery the project already has or the literature
already provides. The output is a per-benchmark, per-product **fit report**, not a score.

| # | Component | Question | How to measure (existing machinery) |
|---|---|---|---|
| F1 | **Coverage fit** | Does *T* cover *P*? | Map the product's use-case spec / traffic sample into the benchmark's theme space; report overlap and the uncovered mass. (Embedding/classifier match; same tooling as Phase-1 rubric mining.) |
| F2 | **Regime fit** | Does Θ match θ\*? | An **assumption audit**: classify, per item/criterion, which regime assumptions it encodes. The Phase-1 **data-dependency classifier** is the prototype — it audits exactly one Θ-axis (data availability) and found 1,791/5,000 items assuming data-unknown. Generalize per axis: data, interface, user type, modality, recency. |
| F3 | **Criterion fit** | Does *S* reward what *w* says matters? | Cross-tab rubric criteria against the product's behavior requirements: criteria that are *anti-correlated* with deployment quality under θ\* (e.g. "asks for X" when X is on file) are flagged as inverted; missing behaviors (e.g. "reads the trend correctly") are flagged as uncovered. Construct-validity checklist ([2511.04703](https://arxiv.org/abs/2511.04703)) applied *relative to C*, not in the abstract. |
| F4 | **Discrimination fit** | Does B separate the candidate models *at their operating point* — and are scores even valid? | Item discrimination / IRT (tinyBenchmarks [2402.14992](https://arxiv.org/abs/2402.14992), Anchor Points [2309.08638](https://arxiv.org/abs/2309.08638)): if the candidate suite saturates the benchmark, it is unfit regardless of topic. Plus a contamination probe (LiveBench-style recency split; surface-cue probe [2410.11672](https://arxiv.org/abs/2410.11672)) — a contaminated score is no score. |

F1/F4 are adaptations of existing ideas; **F2 and F3 are the new content** — no published
audit asks what regime a benchmark *assumes*, conditioned on a product. We discovered F2
empirically (the data-prevalence measurement) before naming it.

---

## 4. Novelty 2 — the Fit Oracle: invariance under regime instantiation

The fit report (§3) is static analysis; it can flag mismatches that don't matter and miss
ones that do. The decisive test is **behavioral**:

> **Fit test.** Apply a *regime-instantiation operator* **G<sub>θ\*</sub>** to the
> benchmark — transform a sample of items so they hold under the product's actual regime
> (inject the data the product would have, switch the interface, add the noise states) —
> and mutate the rubrics accordingly (Direction B's operator `(V, R, P) → (V′, R′)`).
> Then measure, over a fixed model suite:
>
> - **Δscore** — per-model score shift between (V, R) and (V′, R′), and
> - **Δrank** — Kendall τ between the two model rankings, with significance under a
>   noisy judge ([2601.20913](https://arxiv.org/abs/2601.20913)) and perturbation
>   robustness ([2508.11847](https://arxiv.org/abs/2508.11847)).
>
> **If scores and rankings are invariant** under instantiation, the benchmark already
> measures what the deployment regime needs → *fit, use it as-is*.
> **If they shift**, the benchmark is unfit for this product — and the drift is
> **localized to the exact items and criteria that moved**, which is precisely the input
> the generation step needs.

Three properties make this the core methodological novelty:

1. **It is a falsifiable definition of "fit."** "Benchmark B is fit for product C" ⇔
   "B's verdicts are invariant under instantiation of C's regime." No appeal to expert
   intuition; intuition comes back only to *validate the instantiation operator itself*.
2. **Failure is informative, not just diagnostic.** A failed fit test outputs a **drift
   map** — which items, which criteria, which Θ-axis — so Q2 (generation) starts from a
   work-list rather than a blank page. Quality audits and IRT can say "unfit"; only the
   mutation test says *where and why*.
3. **It is already prototyped.** The Phase-2 PoC *is* a fit test at n=2 for one Θ-axis
   (data availability), and it returned "unfit" with the mechanism identified (the
   ask-criteria invert). Direction B's Phase-4 scale-up doubles as the first full-size
   fit-oracle run.

The cross-check from the 2026-06-05 meeting slots in here as the oracle's own sanity
check: a valid instantiation must be **monotone in data quality** (better data ⇒ higher
data-aware score) — if not, the oracle is broken, not the benchmark (vision.md §4,
"hidden-context test").

---

## 5. Novelty 3 — graduated repair, not from-scratch generation

When the fit test fails, today's literature offers one move: build a new benchmark
(AutoBencher et al.). That discards the most expensive asset in evaluation — embedded
expert validation (HealthBench: 48,562 physician-written criteria) — and pays full
validation cost on the replacement. The §3.1 argument of the
[Direction-B review](lit-review/data-grounded-evaluation.md) generalizes into a
**repair ladder**: escalate only when the cheaper rung fails its certification gate (§6).

| Rung | Operation | When | Cost (what needs re-validating) |
|---|---|---|---|
| L0 | **Use as-is** | Fit test passes | Nothing |
| L1 | **Reweight** — keep all items & criteria, change weights to *w* | Drift is confined to weight-sensitive aggregation | Nothing item-level. Direction A's weight-perturbation analysis tells you *in advance* whether L1 can work: if rankings are robust to weight jitter, reweighting cannot fix a rank-level drift and you skip to L2. |
| L2 | **Mutate criteria** — Direction B's operator: moot / induced / urgency per criterion | Drift localizes to criteria with inverted or missing regime assumptions | **Only the delta**: the changed criteria per item, not the benchmark. |
| L3 | **Augment items** — generate new items (+rubrics) for the uncovered mass of F1/F3, keep the rest | Coverage holes, not criterion inversions | New items only, certified against the retained set (§6). |
| L4 | **New benchmark** — from-scratch generation (Direction A §3 machinery; AutoBencher/BenchAgents patterns) | The product is genuinely outside the registry (no benchmark within useful edit distance) | Full validation — the case where from-scratch was the right call all along. |

Two corollaries worth stating as contributions in their own right:

- **Benchmark edit distance.** The validation cost of a trustworthy benchmark scales with
  its *distance from the nearest validated benchmark* (number of mutated/added
  criteria & items), **not with its size**. This is the delta-validation economics from
  the Direction-B review (§3.1.3), promoted to a design principle: minimize edit
  distance, not generation effort.
- **The repair ladder is the product-fit decision procedure.** "Fits an existing
  benchmark vs. needs a new one" stops being binary: the answer is a rung, with a cost
  estimate attached. That is what a product team actually needs.

---

## 6. Novelty 4 — the certification gate and a chain of trust

Every rung's output must pass the same gate before anyone reads its numbers. The gate
reuses Direction A's yardstick and Direction B's controls — assembled, they form a
**certification standard** that does not currently exist in the literature:

1. **Rank preservation on the bridge set.** Items unchanged by the repair (L1–L3 always
   retain some) form a **bridge**: the repaired benchmark must reproduce the reference's
   model ranking on the bridge (Kendall τ primary, Spearman ρ secondary), with
   significance under an imperfect judge ([2601.20913](https://arxiv.org/abs/2601.20913)).
   New/mutated items are then certified *by consistency with the bridge*, not by fiat.
2. **Weight-sensitivity disclosure.** Report rankings as ranges over plausible weightings
   (the 2026-06-05 meeting's open question, operationalized): if the verdict flips under
   defensible weight jitter, the benchmark must say so rather than print a point estimate.
3. **Validity controls shipped with the benchmark** (from the Direction-B review §3.3):
   record-only / partial-input probes ([1803.02324](https://arxiv.org/abs/1803.02324),
   [2410.11672](https://arxiv.org/abs/2410.11672)), counterfactual instantiations
   ([1909.12434](https://arxiv.org/abs/1909.12434)), content-corruption ablations, and
   the monotonicity test — released as part of the artifact, so every consumer can re-run
   the leakage checks.
4. **Delta expert validation.** Human experts see only the changed criteria/items (L2–L3)
   or a calibration sample (L4), with inter-rater agreement reported — the
   clinician-refine pattern (ClinAlign, [2602.09653](https://arxiv.org/abs/2602.09653))
   applied at minimum surface.

Chaining gates yields a **registry with provenance**: an expert-built root (HealthBench)
plus a tree of certified transformations, each edge carrying its measured τ, its
sensitivity report, and its delta-validation record. New products query the registry
(fit test against the nearest node) and extend it (repair + certify). Trust decays along
the path — **provenance depth is tracked, and τ-degradation per hop is an empirical
quantity we measure, not assume** (see threats, §7).

---

## 7. Threats & honest limits

- **The case-level variance bound.** Physician disagreement decomposition
  ([2602.22758](https://arxiv.org/abs/2602.22758)) puts ~82% of HealthBench label
  variance at the case level. Rubric-level repair (L1–L2) cannot fix case-level
  problems; the fit oracle must therefore compare *paired* (within-item) quantities,
  where that term differences out — and the registry must not promise more agreement
  than the human ceiling (κ ≈ 0.85–0.90).
- **Chain drift.** Certifying B′′ against B′ against B compounds error. Mitigations:
  bound provenance depth, re-anchor periodically with small expert audits, and measure
  τ-per-hop empirically before trusting depth > 2. If τ-degradation per hop is large,
  the registry degenerates to "validate everything against the root" — still useful,
  less scalable. This is a *measurable risk*, and measuring it is itself a publishable
  result.
- **Goodhart.** A registry that product teams optimize against invites overfitting to
  generated criteria. Partial defenses: held-out certification items, ArenaBencher-style
  multi-model evolution ([2510.08569](https://arxiv.org/abs/2510.08569)), and the
  contamination probes in F4 — but this is structural, not solvable; disclose it.
- **Judge ceiling.** Rubric judges max out well below perfect (RubricEval: GPT-4o ~56%
  on hard items, [2603.25133](https://arxiv.org/abs/2603.25133)); every gate statistic
  must run through the noisy-judge framework rather than assume a clean grader.
- **Prior-art check before claiming F2/F3 and the fit oracle as novel.** Benchmark
  *quality* assessment exists (construct-validity reviews; BetterBench-style audits
  [verify exact cite]); "benchmark selection for a use case" may exist in fragments
  (model-routing / eval-selection literature). A targeted sweep on *product-conditioned
  benchmark validity testing* is required before the paper claims priority — none of the
  ~120 papers in the two lit reviews does it, which is encouraging but not conclusive.

---

## 8. The claim ladder — keeping the motivation honest

The enticing maximal pitch — *"an automatic agent framework that takes **any** existing
rubric-based benchmark, augments it with data, is **accurate**, and reveals
**never-seen-before** model properties, because rubric mutation is **perfect**"* — is the
right ambition and the wrong sentence. It decomposes into five sub-claims with very
different evidentiary status; the motivation should claim the reachable ones and present
the rest as trajectory, with each escalation licensed by a named experiment (§9).

| Sub-claim | Status | Assessment |
|---|---|---|
| "Automatic agent framework" | **Reachable — engineering, not research risk** | The pipeline is LLM-driven end-to-end already (dependency classifier → phenotype extraction → Synthea-to-spec → mutation → grading); packaging it as an agent framework is work, not uncertainty. |
| "Any rubric-based benchmark" | **Overclaim as stated; bounded version reachable** | The mutation *operator* is general — it needs only atomic criteria, the seam to mutate. The *instantiation engine* is domain-specific (Synthea exists for health; nothing equivalent for law or finance). Defensible: "rubric benchmarks in domains with structured user context," credible only with **two demonstrations** (E5). |
| "Accurate" | **The weakest link — redefine it** | There is no gold reference for a mutated criterion, and hard ceilings exist: rubric judges ~56% on hard items ([2603.25133](https://arxiv.org/abs/2603.25133)), ~82% of HealthBench variance is case-level ([2602.22758](https://arxiv.org/abs/2602.22758)), human κ ≈ 0.85–0.90. Mutation can never be *verified perfect* — only **certified within bounds** (§6). |
| "Never-seen-before model properties" | **Most defensible enticing part — partially demonstrated** | The PoC already surfaced one (a model that *had* the medication in context and still hedged — invisible to text-only eval); the unified **data-use policy profile** is open, with the precise prior-art boundary in §8.2. |
| "Because mutation is perfect" | **Wrong causal story — drop it** | The contribution is the *measurement framework* that makes imperfect mutation usable: the fit test says **where** the benchmark is wrong, certification bounds **how much** to trust the repair. Perfection is neither achievable nor needed. |

### 8.1 The supportable headline

Replace "any" and "perfect" and the claim is both honest and still enticing:

> *An automatic framework that takes a rubric-based benchmark, **measures** whether its
> verdicts survive the product's data regime (the fit test), **repairs** it where they
> don't — with validation cost proportional to the delta, not the benchmark — and in
> doing so measures a model property no existing benchmark reports: the conditional
> data-use policy.*

This position is stronger than "perfect," not weaker: we do not promise the mutation is
right, we promise you can **tell how right it is and what it costs to check** — the only
position the certification literature (noisy judges, ranking brittleness) actually
supports. A pragmatic argument points the same way: the Jan–Feb 2026 wave shows this
space moves in months; a maximal claim that needs two years will be partially eaten
before it ships, while the bounded claim is stakeable this summer.

### 8.2 The "new model property" claim, stated precisely

"Model M always-asks, model N always-trusts" must be claimed carefully, because pieces of
it *are* benchmarked (checked against the B1/B3 sweeps; the two closest counterexamples
re-verified against their abstracts):

- **Data-as-input benchmarks score endpoints only, with data always present.** MedAlign:
  clinician ranking vs. references; MedAgentBench: programmatic task success; EHRNoteQA /
  MedCalc-Bench: answer correctness; EHRSHOT: AUROC; PH-LLM: fixed expert-rubric scores.
  None varies the data state on the same case; none scores the model's *behavior toward
  the data* as distinct from answer quality.
- **The behavioral literature does benchmark asking** — "nobody measures asking" would be
  false. MediQ ([2406.00922](https://arxiv.org/abs/2406.00922), re-verified) varies
  information completeness and lets the model decide whether to ask, but the *scored*
  metric is diagnostic accuracy — asking is instrumental, and the variation runs only
  from incomplete toward complete. Q4Dx scores asking-efficiency over 100/80/50%
  symptom-exposure levels; AbstentionBench scores abstention; RAMDocs / DriftMedQA score
  answer accuracy under conflicting evidence.
- **What is genuinely missing (no exceptions found in the sweeps):** **(1) the USE
  half** — no scoring function anywhere penalizes re-asking for what is already on file
  or rewards correctly using the supplied value; interactive benchmarks treat asking as
  cost-free, and static rubrics (HealthBench) actively *reward* it — nowhere does asking
  become *wrong*. **(2) RECONCILE as scored behavior** — under noisy/conflicting data the
  literature reports *that* models get swayed, not whether flagging the conflict was
  credited as the correct response. **(3) the same-case, cross-state profile** — nobody
  holds the case fixed, sweeps no-data → missing-field → noisy/conflicting → clean on
  injected structured records, and scores the state-appropriate behavior in each.

**Wording for the paper:** *existing interactive benchmarks score whether asking improves
the final answer; none scores whether the model enacts the right policy across data
states — in particular, no existing scoring function ever makes asking* wrong*. We
measure the full ask/use/reconcile profile on the same cases with injected structured
records.*

**Before print:** read the full texts of MediQ and AgentClinic
([2405.07960](https://arxiv.org/abs/2405.07960)) — the latter's abstract mentions
unspecified "patient-centric metrics" — to confirm neither scores question necessity.
Two one-hour reads, cheap insurance on a priority claim.

### 8.3 What licenses each rung (claims ↔ evidence)

| Claim | Licensed by |
|---|---|
| "Benchmark fitness is measurable" | E1 + E2 (drift replicates at scale, with significance) |
| "The framework reveals a new model property" | E2's degradation-curve extension + the §8.2 differentiation |
| "Benchmark repair is affordable" | E3 (repair ≈ rebuild on τ at a fraction of expert surface) |
| "The operator generalizes beyond HealthBench" | E5 (one small transfer) |
| "Any benchmark / registry / chain of trust" | Research program (E4 is the first data point) — present as trajectory, never as result |

**Internship-realistic:** E1–E3, plus E5 at toy scale. **Program-scale:** the registry,
multi-axis regimes, "any benchmark."

---

## 9. First experiments (sequenced, cheap-first)

- **E1 — The first Fit Report (mostly already done, needs assembly).** Target:
  HealthBench vs. a "wearable health assistant" product context. F2 is the
  data-prevalence + dependency-classifier result (~83% data-blind; 1,791 ask-items);
  F3 is the inverted-criteria count from the Phase-1 shortlist; F4 runs IRT on
  published HealthBench per-model scores. Deliverable: a 2-page generated report — the
  template for every future fit query. *Cost: days; no new infra.*
- **E2 — The Fit Oracle at scale (= Direction B Phase 4, reframed).** Regime-instantiate
  100–300 items on the data axis, run the model suite, report Δscore / Δτ with the
  noisy-judge significance machinery, and produce the **drift map**. One experiment now
  serves both the Direction-B paper and the north-star method paper. **Run a reduced
  version (n≈50) first — this is the kill-shot:** the PoC cases were *chosen* to be
  sharp; if drift does not replicate on classifier-flagged items, the motivation
  deflates, and we want to learn that in month one, not month three.
- **E3 — The repair ladder head-to-head.** On the drifted items from E2, compare L1
  (reweight only) vs L2 (mutate) vs L4 (regenerate from scratch with an
  AutoBencher-style baseline) on: bridge-set τ, expert-validation surface (count of
  criteria a physician must read), and wall-clock cost. *Hypothesis:* L2 dominates L4 on
  cost at equal τ — the result that justifies the whole repair-before-rebuild stance.
- **E4 — One chain hop.** Certify a generated benchmark (Direction A §4's rank-preserving
  generation) against HealthBench via a bridge set, then run one further repair on top
  of it and measure τ-degradation at depth 2. First empirical number for chain drift.
- **E5 — Transfer demo (stretch).** Apply the instantiate → mutate → certify loop to a
  second rubric benchmark at n≈20. Cheapest: **HealthBench Professional** (same family;
  its "care consult" tasks are *the* data-hungry cases, vision O7). More convincing for
  generality: a non-health checklist benchmark from Direction A §A1 (TICK-style,
  BiGGen Bench). One small transfer turns "a HealthBench patch" into "an operator,
  demonstrated twice" — and is what licenses any talk of the L4 / registry trajectory.

---

## 10. One-line takeaway

**Fit** becomes a measured invariance ("the benchmark's verdicts don't change when we
instantiate the product's regime"), **generation** becomes graduated repair of the
nearest validated benchmark (cost ∝ edit distance, not size), and **trust** becomes a
certification gate chaining back to expert roots — with Directions A and B as the
already-running machinery for, respectively, the gate and the first regime axis.
