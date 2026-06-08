# Data-Grounded HealthBench

**Working title:** HealthBench-Grounded (HB-G)
**One line:** Extend OpenAI's HealthBench from text-only vignettes to evaluations *conditioned on real longitudinal user data* (wearables + EHR), to expose where the "right answer," the rubric, and model behavior change once a model actually has the patient's data.

---

## 1. Motivation

[HealthBench](https://openai.com/index/healthbench/) and [HealthBench Professional](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf) evaluate LLMs on **free-text health conversations**: the user (a layperson or a clinician) describes everything the model needs to know in natural language, and physician-written rubrics score the reply. This is a strong benchmark, but it bakes in one assumption: **the only thing the model knows is what the user typed.**

Real health AI — the kind that runs on a wearable platform or a connected-health app — does not work that way. It operates with **ambient structured context**: continuous wearable streams (HR, HRV, sleep, steps, SpO₂, activity), a medication list, prior labs, a problem list, allergies, demographics. The moment you add that context, three things change that a text-only benchmark *cannot* measure:

1. **The optimal response changes.** A rubric criterion that rewards *"asks the patient about their recent blood pressure"* becomes **wrong** if the blood pressure is already in context. Now the ideal model *uses* the data; a model that asks should arguably be penalized, and a model that ignores available data definitely should be. Static rubrics silently encode what is *unknown* — and that encoding breaks under data-conditioning.
2. **New failure modes appear** that no text vignette can elicit: misreading a numeric time series, ignoring a documented contraindication, hallucinating data that isn't in the record, over-trusting noisy consumer-sensor data, failing to reconcile conflicting signals (wearable says X, EHR says Y), or botching temporal reasoning over months of longitudinal data.
3. **New safety and equity surfaces open up.** Data can *flip urgency* (an abnormal lab → an emergency-referral situation). And a demographically diverse cohort lets us ask whether adding data helps or hurts *across subgroups*.

**Thesis.** A health LLM benchmark that ignores user data systematically mis-scores the behaviors that matter most in deployment. We can (a) quantify how much HealthBench's ideal answers and rubrics shift under real data-conditioning, (b) build a failure taxonomy for how models (mis)use structured data, and (c) ship an **automated pipeline** that generates data-grounded eval items and rubrics at scale, validated against physician judgment.

**What we've found so far (Phase 1–2).** Of the 5,000 HealthBench conversations, **1,791 contain at least one criterion that rewards *asking for* information a record could supply.** Conversely — and the paper does not report this, so we measured it — **only ~1 in 6 conversations (≈16.8%; 95% CI 14.1–20.0) already *contain* the patient's own structured data** (a medication they take, lab/vital values, or a record excerpt), and **virtually none (~0%) contain wearable/sensor data**; i.e. **~83% are effectively data-blind.** We measured this with an **LLM judge prompted to flag, per category (medication / labs / vitals / wearable / EHR-record), whether a conversation contains that kind of data** — not just names it as a topic — calibrated on a random sample (n=600; a regex census agrees as a lower bound). So the benchmark mostly *asks for* data it almost never *supplies*: strong evidence the static "right answer" is built on a data-unknown assumption. (Detail: [user-data-prevalence.md](../experiments/data-grounded-healthbench/reports/user-data-prevalence.md).) On a 30-entry data-grounded proof-of-concept, the original rubric scored a data-*blind* answer **59%** on average but the (correct) data-*aware* answer only **42%** — it actively *penalized* using the record in **19/30** entries (some answers went negative). A data-conditioned rubric restored the data-aware answer to **71%**.

The nuance that matters most: this is **not** merely "lost points for not asking." Static rubrics **conflate two different things** — *did the model ask the right questions?* and *did it correctly use what it already knows?* — and end up rewarding the first while penalizing the second. Data-conditioning **separates them**, shifting the measured axis from *"asks the right questions"* to *"correctly uses available information"* — the capability that actually matters in deployment. (Bonus: the residual score under the mutated rubric exposes real model failures the text-only setup hid — e.g., a model that *had* the medication on file but still hedged.)

**Is the original rubric "wrong"? No — and that is the point.** Within its own scope the rubric is correct: it was written assuming the model knows only what the user typed, and under *that* assumption, *asking* for missing history is genuinely the right behavior. The problem is that the assumption is **load-bearing and invisible** — a static rubric silently bakes "the data is unknown" into its definition of the correct answer. Real deployment violates exactly that assumption: a wearable or connected-health assistant *starts* with the record. So the benchmark's "correct answer" is pinned to a regime the product never operates in. We are not patching a buggy rubric; we are **making the deployment regime measurable**, where re-asking for known data is no longer free and using the record is expected. (This is why the score-drop, though *expected and almost trivial on its own*, is still a valid motivation: it shows the static "right answer" is bound to the data-unknown assumption and silently fails the moment a real system has data.)

**The behavior we actually want is *conditional*.** "Correctly uses available information" is **not** "always uses data." It is *ask when the data is absent, use it when it is present, and reconcile/flag when it conflicts.* A good assistant should **degrade gracefully** across whatever data it happens to have. That reframes the target from a single right answer into a **policy over data states** — and it is what turns one expected observation into the concrete studies in §4.

This is a natural fit for Meta: wearable + sensing platforms are exactly the deployment context, and open models (Llama) can be a first-class evaluation target alongside frontier APIs.

---

## 2. Research questions

- **RQ1 — Rubric drift.** What fraction of HealthBench criteria are *data-dependent*, and how do ideal responses + rubrics change when conditioned on a real patient profile? (Metrics: % criteria invalidated, % new criteria induced, urgency-flip rate.)
- **RQ2 — Model behavior.** Do frontier and open LLMs actually *use* available structured data — or ignore it, hallucinate it, or misread it? Build a behavioral failure taxonomy and measure each mode's prevalence.
- **RQ3 — Automation.** Can we generate data-grounded eval items + mutated rubrics automatically, with quality that agrees with physician raters?
- **RQ4 — Equity (stretch).** Does data-conditioning change subgroup performance (by age, sex, comorbidity burden)? Partially addressable now by generating Synthea subpopulations; a real diverse cohort (future) is needed for a strong fairness signal.
- **RQ5 — Conditional competence across data states.** Does a model enact the right *policy* across the spectrum *no data → relevant field missing → data present but noisy/conflicting → data present and clean*? I.e., does it **ask** when data is absent and **use** it when present, rather than always-ask or always-trust? (Metric: per-state score; a "graceful-degradation" curve.) See §4 N2.
- **RQ6 — Relevance under a full record.** Given a *whole* record (mostly irrelevant to the question), can the model find and use the decision-relevant fields without being distracted by — or over-trusting — the rest? (Metric: relevant-field hit rate; distractor-induced error rate.) See §4 N3.
- **RQ7 — Numeric & time-series grounding.** Can models read fine-grained sensor streams (trends, units, noise), not just described symptoms? (Metric: numeric-claim accuracy vs. ground truth.) *Gated on adding sensor streams (future; §7).* See §4 N4.
- **Construct-validity question (cross-cutting).** How much of any measured effect is an artifact of *how we synthesize the data* (relevance engineered by construction)? See §4 N1.

---

## 3. Core idea: data-conditioned evaluation

HealthBench is a static text vignette `V` with rubric `R`. We turn it into a function of patient data:

```
(V, R)                                   ← original HealthBench item
        ── data-dependency analysis ──▶  D = which data fields are decision-relevant?
        ── retrieve / instantiate ────▶  P = a real (or synthetic) patient with those fields
        ── context construction ─────▶  V' = V augmented with P's data
        ── rubric mutation ──────────▶  R' = R with moot criteria removed, data-grounded criteria added, urgency reweighted
        ── physician validation ─────▶  R' accepted / corrected
                                         ▶ evaluate models on (V', R'); compare deltas vs (V, R)
```

> **Framing note.** HealthBench vignettes are fictional/templated, so "matching a real user" is *not* about finding one true person. It is **counterfactual instantiation**: filling the latent variables the vignette left unspecified with a *realistic, internally-consistent, real-world* data profile. That reframing avoids a hopeless 1:1 matching problem and is more defensible scientifically.

> **Why this is automatable — and why it's a *benchmark*, not a model.** Synthesizing a realistic record that *fits* a conversation (conversation → data) is far easier to automate than the inverse a deployed model faces — correctly *interpreting* arbitrary, noisy real data (data → answer). The benchmark only has to *specify* what good looks like, offline, for cases we choose; a model must *produce* it, online, for every input. That asymmetry is why we can auto-generate the evaluation even though we can't auto-generate a perfect model — and the eval still *helps* model-building, as the objective and error-analysis lens that turns "use the data well" into an explicit, checkable target. **Caveat:** synthesizing the data is the easy half; auto-mutating a *clinically correct* rubric is the hard half, and is exactly what physician validation (§6, C3) gates.

---

## 4. Nuances & study directions (beyond the headline)

The headline — *a static rubric scores a data-aware answer lower* — is **expected, and on its own almost trivial**: many criteria reward asking for meds/history, so once the record is supplied the model rightly stops asking and "loses" those points. That observation is the *symptom*, and it is enough to motivate the project (see §1). The substance is in the questions it opens. Each direction below pairs a **concrete study we can run on synthetic data** with the **literature it connects to**, so each doubles as a lit-review entry point.

**N1 — Where does the injected data come from, and is the test fair? (construct validity).**
The obvious objection: *you handed the model exactly the data the conversation needed, so of course using it helps.* That is fair, and it is true by construction — our records are synthesized **from the original query + the physician-written rubric + established clinical guidance**, so relevance is *engineered*. That is a *feature* for a controlled diagnostic (we know the ground-truth-relevant fields and can mutate the rubric against them) but a **threat to external validity** (real records aren't curated to the question). It must be stated honestly and studied, not hidden.
- *Study:* (a) ablate data **provenance** — generate records conditioned on the query only vs. query+rubric vs. guidance-augmented — and measure how much the rubric mutation and the score-shift depend on how the data was made; (b) pair each case with **adversarially irrelevant** and **partially-relevant** controls (feeds N3) to show the effect isn't pure leakage.
- *Lit hooks:* counterfactual / controllable clinical-record synthesis; construct validity in benchmark design; dataset shortcut features & spurious cues ("Clever Hans"); contamination/leakage critiques.

**N2 — The data-state spectrum & graceful degradation.**
"Correct use" is a *policy*, not a binary. Four conditions, all synthesizable by controlling what we inject: **(1) no data**, **(2) data present but the relevant field is missing**, **(3) data present but low-quality** (noisy / stale / wearable-vs-EHR conflict), **(4) data present, complete, clean**. The correct behavior differs per state — *ask* in (1)–(2), *use* in (4), *reconcile and flag uncertainty* in (3) — which is exactly the conditional target from §1. A model that always-asks looks fine in (1) but fails (4); one that always-trusts looks fine in (4) but is dangerous in (3).
- *Study:* build the **same case across all four states**, score each against a state-appropriate (mutated) rubric, and plot the degradation curve per model. The benchmark then rewards the conditional policy rather than any single answer.
- *Lit hooks:* robustness to missing/noisy features; selective prediction / abstention & calibration; uncertainty-aware and conflicting-evidence clinical decision support.

**N3 — Relevance under a full record dump (the realistic interface).**
Today's PoC injects *only* the relevant fields. Real systems hand the model a *whole* longitudinal record, most of which is irrelevant to any one question. The capability under test shifts from "use the data" to **selection**: find the decision-relevant fields amid distractors, without over-trusting an irrelevant value or losing the key one in a long context. This is the natural extension of the context-interface axis (§6, C4).
- *Study:* hold the relevant fields fixed; vary the **volume and realism of surrounding irrelevant record** (k distractor fields → full synthetic history); measure relevant-field hit rate and distractor-induced error rate against context length and interface (raw dump vs. structured summary vs. retrieval).
- *Lit hooks:* long-context distractor robustness / needle-in-a-haystack / lost-in-the-middle; retrieval-augmented generation over clinical notes; clinical information extraction.

**N4 — Fine-grained wearable time-series.**
The hardest and most Meta-relevant axis, and the one Synthea cannot supply yet. High-frequency HR/HRV/sleep/steps/SpO₂ demand **numeric and temporal reasoning** (trends over weeks, units, noise, downsampling) that no text vignette can probe.
- *Study:* once sensor streams are added (future; §7 datasets / §8 pipeline), test numeric-claim accuracy and trend interpretation under different **serializations** (raw samples vs. per-window summaries vs. derived features), and measure context-length sensitivity (ties §6, C5).
- *Lit hooks:* LLMs for time-series & numeracy; wearable-signal interpretation; serialization of numeric data for LLMs; tool-use / code-execution for computation.

Together these turn one expected observation into a structured agenda: from *does the static score drop?* (yes, trivially) to *can a model enact the right data-conditional policy (N2), find the signal inside a real record (N3), reason over real sensor streams (N4) — and are we even measuring that fairly (N1)?* Those are the capabilities that decide whether a data-equipped health assistant is safe to deploy.

---

## 5. Opportunities (what's novel / publishable)

| # | Opportunity | Why it matters |
|---|-------------|----------------|
| O1 | **Quantify rubric drift** under data-conditioning | First measurement of how much a leading health benchmark mis-scores once data is present. A single headline number ("X% of HealthBench criteria are data-dependent") is paper-worthy. |
| O2 | **Numeracy & time-series grounding** | Tests whether LLMs can read wearable/lab *numbers and trends*, not just reason about described symptoms — a capability text benchmarks can't probe. |
| O3 | **Automated, data-conditioned rubric generation** | A reusable method to mutate/extend rubrics given a patient profile; the reusable artifact is the real contribution, not any single dataset. |
| O4 | **Safety surface: data-driven urgency** | Contraindications, drug interactions, abnormal labs that *change the correct action* (ties directly to the emergency-referral theme). |
| O5 | **Equity/fairness analysis** *(stretch / future)* | Synthea subpopulations give a first cut; a real diverse cohort (e.g. All of Us, which over-samples underrepresented groups) would give subgroup deltas most benchmarks can't support. |
| O6 | **Over-/under-reliance taxonomy** | Distinguish models that ignore data, invent data, or over-trust noisy sensors — directly actionable for model builders. |
| O7 | **Clinician-facing extension (HealthBench Professional)** | "Care consult" and "medical research" clinician tasks are *the* data-hungry cases; EHR-grounding them is high-value and underexplored. |

---

## 6. Challenges & risks (with mitigations)

| # | Challenge | Mitigation |
|---|-----------|------------|
| C1 | **Data governance** (the reason we start synthetic). Real cohorts like All of Us **cannot be exported** from their Workbench; row-level data and re-identification attempts are prohibited; outputs pass disclosure review. | **Start fully synthetic (Synthea)** so the benchmark + pipeline are openly reproducible with zero governance friction. A real-data cohort is *future work* (§9 Phase 5), not a current dependency — and would be reported only as in-environment aggregates. |
| C2 | **Matching is ill-posed** (fictional vignette ↔ structured record). | Reframe as *counterfactual instantiation* (§3); define explicit phenotype → cohort queries; handle no-match / multi-match; allow synthetic generation-to-spec. |
| C3 | **Who validates the mutated rubric?** Auto-mutation can introduce clinical errors. | Physician-in-the-loop on a calibration sample; report inter-rater agreement and auto-vs-human agreement before scaling. |
| C4 | **Injection realism.** Concatenating a data dump ≠ how real systems present context (RAG, structured summaries, tool calls). | Treat *context interface* as an explicit experimental axis: raw dump vs. structured summary vs. tool/retrieval access. Report sensitivity. |
| C5 | **Serializing time-series for an LLM** (units, downsampling, long context). | Define a canonical serialization (per-modality summaries + salient windows); document downsampling; measure context-length effects. |
| C6 | **Grader reliability.** A model grader must now verify *numeric* claims against the provided data. | Validate the grader on data-grounded criteria specifically; add deterministic checks for numeric/lookup criteria where possible. |
| C7 | **Temporal alignment.** Vignettes are snapshots; data is longitudinal. | Define an explicit "as-of" timestamp per item; align data windows to it. |
| C8 | **Licensing.** HealthBench code/data terms vs. dataset terms differ. | Keep HealthBench-derived rubrics and dataset-derived records in separate, clearly-licensed artifacts; verify redistribution terms before release. |

---

## 7. Candidate datasets

**Decision: Synthea is the dataset for this project.** Fine-grained real sensor streams (PMData/WESAD/UK Biobank) and real cohorts (All of Us) are explicitly *out of scope for now* and listed only as future options.

| Dataset | EHR | Wearables | Access | Exportable? | Role here |
|---|---|---|---|---|---|
| **[Synthea](https://github.com/synthetichealth/synthea)** | ✅ synthetic FHIR/CSV (conditions, meds, labs, vitals, encounters) | ⚠️ vitals/observations, no native high-frequency sensor streams | Fully public | ✅ | **The project's data source** — develop + open-source the pipeline, generate patients to spec |
| **[All of Us](https://www.researchallofus.org/data-tools/data-sources/)** | ✅ OMOP CDM | ✅ Fitbit/Apple, 59k+ participants | Researcher Workbench (cloud) | ❌ in-environment only | *Future / optional* — no DUA in place; aggregate-only if ever pursued |
| **[MIMIC-IV](https://physionet.org/content/mimiciv/)** | ✅ rich, ICU/ED | ❌ | PhysioNet credentialed | ⚠️ credentialed | *Future / optional* — high-acuity, lab-heavy cases |
| **PMData / WESAD / UK Biobank** | varies | ✅ research-grade wearable | Public / application | varies | *Future / optional* — only if fine-grained sensor streams become needed |

**Why Synthea now:** it gives EHR-style structured data (problem list, meds, allergies, labs, vitals) we can **generate to spec** for any phenotype, with zero governance friction and a fully open, reproducible artifact. Its limitation is the absence of high-frequency sensor streams (continuous HR/HRV/sleep) — acceptable for the first phase, since the most decision-relevant fields (labs, meds, allergies, conditions, vitals) are well covered. Rich sensor time-series is a deliberate *future* extension, not a blocker.

---

## 8. Pipeline (the artifact we build)

1. **Rubric mining** — parse HealthBench / Professional JSONL into a structured index: `{example_id, conversation, theme[], criteria:[{text, axis, points, tags}]}`; compute descriptive stats.
2. **Data-dependency classifier** — per example/criterion, label whether it is data-dependent, *which* data fields would change the ideal answer, and the *direction* of change (criterion becomes moot / new criterion induced / urgency shifts). Validated against a hand-labeled seed set.
3. **Phenotype extraction** — convert the vignette into a structured query (conditions, demographics, presenting complaint, decision-relevant fields `D`).
4. **Cohort instantiation (Synthea)** — generate a patient to spec that matches the phenotype *and* carries the fields in `D` (conditions, meds, allergies, labs, vitals). (Concept-set queries against a real OMOP cohort are deferred to future work.)
5. **Context construction — two interfaces, tested head-to-head.** Serialize `P`'s data into `V'` under **(a) raw dump** (structured records inlined verbatim) and **(b) structured summary** (a condensed, model-readable précis). Both are first-class experimental conditions; tool/retrieval access is a later ablation.
6. **Rubric mutation** — derive `R'`: remove moot criteria, add data-grounded criteria (e.g., *"correctly interprets the 3-month rising resting-HR trend"*, *"flags the documented penicillin allergy against the suggested antibiotic"*), reweight urgency.
7. **Validation** — *no physician access in this phase.* Use a **proxy validation** (multi-model judge ensemble + self-consistency checks) to gate auto-mutated rubrics now; physician-in-the-loop validation is a later milestone (§9 Phase 3).
8. **Evaluation & analysis** — run the HealthBench model suite (§9 Phase 4), grade, compute deltas vs. baseline, build the failure taxonomy.

---

## 9. Phase plan

### Phase 0 — Setup (Week 1)
- Pull HealthBench + HealthBench Professional from [openai/simple-evals](https://github.com/openai/simple-evals); confirm licenses/terms.
- Stand up Synthea locally; sanity-check FHIR/CSV output.
- Repo scaffold (§10).

### Phase 1 — Rubric analysis & data-dependency mapping *(the first step you asked for — detailed below)*
This is the diagnostic that justifies the whole project; it produces a number and a shortlist.
- **1.1** Flatten all rubrics into a single table (example_id, turns, theme tags, per-criterion text/axis/points/tags). Compute: criteria-per-example, axis distribution (recall HealthBench skews ~39% completeness, ~33% accuracy, ~16% context-awareness), theme distribution, point distribution.
- **1.2** Define a **data-dependency taxonomy**: wearable streams (HR/HRV/sleep/steps/SpO₂/activity), vitals, labs, medications, problem list, allergies, demographics, family history, immunizations.
- **1.3** Build an **LLM data-dependency classifier** (strict JSON schema output) that tags each example/criterion with `{data_dependent: bool, fields: [...], change_type: moot|induced|urgency}`. Calibrate on a hand-labeled seed (~50–100 examples); report agreement.
- **1.4** **Quantify enrichability** — what % of HealthBench is data-enrichable, concentrated in which themes/axes? *Hypothesis:* context-seeking, health-data-tasks, emergency-referrals themes; context-awareness & completeness axes. **This % is a headline finding.**
- **1.5** Produce a **ranked shortlist** of high-value enrichable entries + their data-dependency profiles.
- **Tight demo (do early):** take ~20 items whose rubric contains a context-seeking criterion (*"ask about X"*), supply `X` via injected data, re-run a model, and show the original rubric now mis-scores. This single experiment validates the thesis fast and cheaply.

### Phase 2 — Instantiation & proof-of-concept (Weeks 3–4)
- Implement phenotype extraction + **Synthea generate-to-spec** instantiation.
- **5–10 fully worked examples**: vignette → instantiated Synthea patient → augmented prompt (**both raw-dump and structured-summary interfaces**) → model run → **side-by-side old vs. new rubric** → documented gap. This proof-of-concept de-risks everything downstream.

### Phase 3 — Rubric mutation + proxy validation (Weeks 5–7)
- Automate rubric mutation; gate it with **proxy validation** (multi-model judge ensemble + self-consistency) since physician raters aren't available yet. Define the protocol so a physician calibration round can slot in later.

### Phase 4 — Scale + evaluate (Weeks 8–10)
- Scale the Synthea benchmark; run the **HealthBench model suite** (below); compare **raw-dump vs. structured-summary** interfaces; build the failure taxonomy.

**Evaluation targets — the model suite reported in the HealthBench paper:**
- **OpenAI:** GPT-3.5 Turbo, GPT-4o, GPT-4.1, o1, o3
- **Other frontier:** Claude 3.7 Sonnet (extended thinking), Gemini 2.5 Pro, Grok 3, Llama 4 Maverick

> Substituting current successors (e.g. the latest Claude / Gemini / Llama / GPT releases) is fine where the paper's exact snapshot is unavailable — note any substitution. Reusing this suite keeps our data-grounded scores directly comparable to the published HealthBench baselines. Note the paper's models are **weakest on completeness and context-awareness** — precisely the axes data-conditioning stresses, so this is where we expect the largest deltas.

### Phase 5 — Future / optional: real-cohort track + write-up (Weeks 11+)
- *Optional, not a current dependency.* If a real cohort (e.g. All of Us) is later pursued, port the validated pipeline into its Workbench and report aggregate, disclosure-reviewed results (incl. subgroup/equity analysis). Add the physician-validation round. Draft paper.

---

## 10. Repo structure

This document lives in a **research-log monorepo** ([top-level README](../README.md)).
Ideas and lit-review live in `docs/`; paper drafts in `latex/`; the actual work is a set
of self-contained experiments. The pipeline below is implemented in experiment #1,
`data-grounded-healthbench`:

```
Auto-Health-Bench/
├── docs/                              # idea docs (this file) + lit-review
├── latex/                            # paper drafts (Overleaf-compatible)
└── experiments/
    └── data-grounded-healthbench/    # ← the pipeline of §8 lives here
        ├── src/
        │   ├── rubrics/              # parsing + indexing HealthBench
        │   ├── dependency/          # data-dependency classifier + taxonomy
        │   ├── phase2/              # instantiation, rubric mutation, grading, reporting
        │   ├── analysis/           # user-data prevalence measurement
        │   └── docx/               # plain-language overview generator
        ├── data/                   # downloaded HealthBench (gitignored) + license notes
        ├── results/                # deltas, score matrices, shortlists
        └── reports/                # method logs / written-up findings
```

Future explorations (phenotype → cohort matching, context-interface variants, model-suite
eval, real-cohort track) land as **new experiment folders** alongside this one rather than
as new top-level `src/` modules.

---

## 11. Deliverables & success metrics

- **D1** Rubric analysis report + the *enrichability %* (RQ1).
- **D2** Open-source data-grounded benchmark on **Synthea** + the generation pipeline (RQ3).
- **D3** Model failure taxonomy with prevalence, across the HealthBench model suite and **both context interfaces** (RQ2).
- **D4** *(future)* Real-cohort aggregate + subgroup/equity results (RQ4).
- **Success:** measurable score deltas between text-only and data-grounded evaluation across the suite; raw-dump vs. structured-summary comparison; ≥1 actionable failure mode for model builders; proxy-validated rubric mutations (with a physician-validation round defined for later).

---

## 12. Decisions (resolved)

1. **Dataset** — **Synthea only** for this phase. No real or fine-grained sensor streams now; All of Us / MIMIC / wearable research sets are future/optional with no DUA in place.
2. **Context interface** — test **both raw dump and structured summary** head-to-head as first-class conditions; tool/retrieval access is a later ablation.
3. **Physician access** — **not now.** Use proxy validation (multi-model judge ensemble + self-consistency) in the interim; physician-in-the-loop validation is a later milestone (Phase 3/5).
4. **Real cohort (All of Us, etc.)** — **not required**, no agreement in place; treated as future work (Phase 5).
5. **Model suite** — the **HealthBench-paper suite**: GPT-3.5 Turbo, GPT-4o, GPT-4.1, o1, o3, Claude 3.7 Sonnet, Gemini 2.5 Pro, Grok 3, Llama 4 Maverick (substitute current successors where a snapshot is unavailable; note substitutions).

Remaining items to settle as we go: serialization details for each context interface; proxy-validation acceptance threshold; size of the hand-labeled seed set for the dependency classifier.

---

## 13. References

- HealthBench — [OpenAI announcement](https://openai.com/index/healthbench/) · [paper (PDF)](https://cdn.openai.com/pdf/bd7a39d5-9e9f-47b3-903c-8b847ca650c7/healthbench_paper.pdf) · [arXiv:2505.08775](https://arxiv.org/pdf/2505.08775)
- HealthBench Professional — [OpenAI (PDF)](https://cdn.openai.com/dd128428-0184-4e25-b155-3a7686c7d744/HealthBench-Professional.pdf)
- Code/data — [openai/simple-evals](https://github.com/openai/simple-evals/blob/main/healthbench_eval.py)
- All of Us — [Data Sources](https://www.researchallofus.org/data-tools/data-sources/) · [Researcher Workbench](https://www.researchallofus.org/data-tools/workbench/) · [Fitbit data in All of Us (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9811842/) · [wearables dataset, Nature Medicine](https://www.nature.com/articles/s41591-026-04352-3)
- Synthetic / other data — [Synthea](https://github.com/synthetichealth/synthea) · [MIMIC-IV](https://physionet.org/content/mimiciv/)
- HealthBench in practice — [arXiv:2509.02594](https://arxiv.org/html/2509.02594v2)
