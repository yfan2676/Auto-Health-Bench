# Literature review — Direction B: Data-grounded evaluation

> **Scope.** The literature behind **Direction B** of [Auto-Health-Bench](../../README.md):
> *what changes when a health benchmark stops being text-only and is conditioned on the
> patient's own structured data?* This is the companion review to the Direction-B idea doc
> [`../vision.md`](../vision.md). Direction A's literature (automatic rubric generation,
> buckets A1–A7) lives in [`auto-rubric-generation.md`](auto-rubric-generation.md); the two
> meet at *data-conditioned rubric generation* (the **A∩B** intersection), discussed in §3.
>
> **Coverage.** Recent work is prioritized (2024–2026, preprints included); a few
> foundational older works are kept where they anchor a sub-field or directly bear on our
> design. Last swept **2026-06**.
>
> **Verification legend.** **✓** = citation opened and confirmed this session (title,
> authors, date, central claim checked against arXiv / the journal page). **[lead]** =
> surfaced by the sweep but not individually re-opened — treat as a lead and verify before
> any formal citation. Two closest-competitor framings (2503.23339, 2601.18706) were
> **personally re-read and corrected** against an over-reading in the sweep — see §5.
>
> **Bucket map.** B1 = the competitor landscape; **B2–B5 correspond one-to-one to the
> N1–N4 themes** in [`../vision.md`](../vision.md) §4 (construct validity / data-state
> policy / long-context relevance / numeric grounding); B6 = the synthetic-data engine.

---

## §1. Landscape at a glance

HealthBench and its kin grade a model on **what the user typed**. Direction B asks what
happens once the model also holds the patient's record. As of mid-2026, three things are
**largely settled** by the surrounding literature:

1. **Feeding LLMs real or simulated structured patient data is well-trodden.** Longitudinal
   EHRs (MedAlign, EHRSHOT, EHRNoteQA), live FHIR environments (MedAgentBench), interactive
   clinical agents (AgentClinic), and wearable streams (PH-LLM, Health-LLM, PHIA) are all
   established evaluation substrates. "Evaluate a health LLM with the patient's own data in
   context" is **not** novel on its own.

2. **Per-case / instance-specific medical rubrics are now generated automatically** — but
   from the *conversation, guideline evidence, or a synthetic case*, not from an injected
   real record (MedDialogRubrics, Automated Medical-Dialogue Rubrics, Health-SCORE; see also
   Direction A §A2/§A4). The criteria adapt to the *task*, not to *what the data makes
   known*.

3. **LLMs are demonstrably weak at the capabilities data-conditioning stresses.** They are
   distracted by irrelevant context and lost in the middle of long inputs (B4), poor at
   abstaining or asking when information is missing (B3), and near-random at multi-step
   numeric/time-series reasoning (B5). The behaviors our benchmark would score are exactly
   the ones the field shows are unsolved.

What is **still open** — and where our idea should live:

- **Data-conditioned rubric *mutation*.** Nothing in this corpus changes a rubric's
  *criteria* because an injected record made them moot, induced new data-grounded ones, or
  flipped urgency. The nearest neighbors condition the *model input* (PH-LLM, MedAgentBench),
  decompose rubric *format* (Adaptive Precise Boolean rubrics), or generate *per-case*
  rubrics from the task — **none mutate the same item's rubric on the record.** This is the
  A∩B white space, and it is the cleanest open claim.
- **Competence as a *policy over data states* (graceful degradation).** The ingredients
  exist in isolation — abstention, clarification-asking, conflict reconciliation — but no
  medical eval varies *data-state quality* on one axis and scores the *state-appropriate
  behavior* on the other. The unified framing is open (B3).
- **A *clinical* full-record distractor benchmark with a context-interface axis.** Long-context
  and distractor robustness are heavily studied in general domains and partially in medicine,
  but no benchmark combines a full longitudinal record, controlled distractor volume, and the
  raw-dump vs. summary vs. retrieval comparison (B4).

The user's prior — *"auto-rubric is crowded; rubrics-with-user-data is less explored"* — holds,
**with a sharpened edge**: it is not "rubrics from health data" that is open (that is closing
fast), it is *rubrics that change when the data is supplied.* See [§3 Implications](#3-implications--the-gap-and-an-actionable-plan).

---

## §2. Thematic buckets

Direction-B analogue of Direction A's A1–A7. Buckets B1–B6; B2–B5 ↔ vision §4 N1–N4.

### B1 — Data-grounded & EHR-conditioned clinical LLM evaluation (the competitor landscape)

*The bucket that decides the gap. Who already evaluates health LLMs with the patient's
structured data — and does anyone condition the* scoring *on it, not just the input?*

**(a) Structured-record-as-input benchmarks — condition the model input, score by task accuracy.**
- **✓ MedAlign** ([2308.14089](https://arxiv.org/abs/2308.14089); Fleming et al., AAAI'24) —
  983 clinician-written instructions over **276 real longitudinal EHRs**; graded by clinician
  ranking against references. Conditions the *input* on the full record; the scoring is a fixed
  per-instruction reference, **not** a rubric that mutates on the data. The canonical ancestor.
- **✓ EHRNoteQA** ([2402.16040](https://arxiv.org/abs/2402.16040); Kweon et al., NeurIPS'24
  D&B) — 962 clinician-refined QA pairs over MIMIC-IV discharge summaries, many needing info
  spread across notes; correlates with clinicians (Spearman 0.78). A reusable source of
  decision-relevant questions + gold answers (also B4).
- **EHRSHOT** ([2307.02028](https://arxiv.org/abs/2307.02028); Wornow et al., NeurIPS'23 D&B)
  [lead] — longitudinal *structured* EHR (6,739 patients) with 15 prediction tasks; foundation-model
  few-shot eval scored by AUROC. A record substrate, not a generative-rubric competitor.
- **✓ MedCalc-Bench** ([2406.12036](https://arxiv.org/abs/2406.12036); NeurIPS'24) — patient note →
  computed clinical value, scored by exact answer. The numeric/lookup leg of data-grounding (also B5).

**(b) Agentic clinical benchmarks — model must gather/use patient data; score = task success.**
- **✓ MedAgentBench** ([2501.14654](https://arxiv.org/abs/2501.14654); Jiang et al., NEJM AI'25,
  Stanford) — 300 physician-written, patient-specific tasks in a **live FHIR-compliant virtual
  EHR** (100 profiles, 700k+ elements); best model ≈70%. The strongest "agent must use the
  structured record" benchmark — but conditions the *task*, not a clinical-advice *rubric*.
  Reusable FHIR environment.
- **✓ AgentClinic** ([2405.07960](https://arxiv.org/abs/2405.07960); Schmidgall et al., npj
  Digital Medicine'26) — multimodal sequential patient/doctor agents across 9 specialties; model
  gathers data under incomplete info, scored by diagnostic accuracy. Competes on interactive
  data-gathering, not rubric mutation (also B6 for its patient-agent construction).
- **3MDBench** ([2504.13861](https://arxiv.org/abs/2504.13861); EMNLP'25) [lead] — 3,013
  telemedicine cases with a temperament-driven Patient Agent + Assessor Agent grading dialogue
  quality; injecting CNN predictions into context boosts F1. Conditions the *model*, not the rubric.

**(c) Wearable / personal-health-data conditioned eval.**
- **✓ PH-LLM (Towards a Personal Health LLM)** ([2406.06474](https://arxiv.org/abs/2406.06474);
  Cosentino et al., Nature Medicine'25, Google) — Gemini fine-tuned on wearable sleep/fitness
  time-series; 857 expert case studies scored by **domain-specific expert rubrics**. The closest
  "evaluate with the user's own data + rubric" prior art — but the rubrics are **fixed expert
  standards** applied to personalized outputs; they are *not* mutated per individual's data.
  The key paper to differentiate against (also B5).
- **RxSafeBench** ([2511.04328](https://arxiv.org/abs/2511.04328)) [lead] — medication-safety
  cases (contraindication + drug–drug-interaction) testing the best med *given patient context*;
  scored by MCQ correctness. The allergy/med-list-collision scenarios are exactly our
  urgency-flip motivation; reusable safety cases.

**(d) The bullseye — does the *rubric* change with the injected data? (nearest neighbors).**
- **✓ Adaptive Precise Boolean rubrics — "A Scalable Framework for Evaluating Health Language
  Models"** ([2503.23339](https://arxiv.org/abs/2503.23339); Mallinar et al., Google;
  Mar 2025, rev. Feb 2026) — decomposes rubrics into minimal boolean checks; ~50% faster eval,
  higher inter-rater agreement. **Correction to the sweep:** "adaptive" refers to *boolean
  decomposition*, and "patient-specific health information" is the *LLM's input* — the abstract
  does **not** describe criteria that become moot or urgency that flips on a record. A rubric-*format*
  improvement to reuse, **not** a data-conditioned-mutation competitor.
- **✓ Health-SCORE** ([2601.18706](https://arxiv.org/abs/2601.18706); Yang et al., Jan 2026) —
  scalable auto-generation of health rubrics for RL reward / in-context use. **Correction to the
  sweep:** the abstract shows *scalable generation*, with **no** evidence of personalized /
  record-conditioned rubric selection. A generation method (shared with Direction A §A4), not a
  data-mutation competitor.
- **Cross-reference (Direction A §A4):** **MedDialogRubrics** ([2601.03023](https://arxiv.org/abs/2601.03023)),
  **Automated Rubrics for Medical Dialogue** ([2601.15161](https://arxiv.org/abs/2601.15161)),
  **ClinAlign** ([2602.09653](https://arxiv.org/abs/2602.09653)) — all generate *instance-specific*
  medical rubrics, but from **synthetic cases or guideline evidence**, not from an injected
  *structured real record*; none describe moot/induced/urgency-flip semantics on the same item.

> **B1 takeaway.** Data-grounded health-LLM *evaluation* is crowded, and *instance-specific
> medical rubric generation* is crowding fast. But **no paper in this corpus mutates a given
> item's rubric because a patient record was injected** — making existing criteria moot, adding
> data-grounded ones, or flipping urgency. That precise operation is the open A∩B claim.

### B2 — Construct validity & leakage *(vision §4 N1)*

*Is the test fair when we synthesize the record* to fit *the question? The records are built
from the query + the physician rubric + clinical guidance, so relevance is engineered by
construction. This bucket is how we frame and defend that honestly.*

- **✓ Measuring What Matters: Construct Validity in LLM Benchmarks** ([2511.04703](https://arxiv.org/abs/2511.04703);
  Bean et al., NeurIPS'25 D&B) — review of 445 benchmarks; widespread construct-validity failures;
  an 8-point checklist. The citation to *name* our threat and state precisely the construct we
  claim ("ability to integrate available structured data into a guideline-grounded answer").
  *(Shared with Direction A §A5.)*
- **✓ Medical LLM Benchmarks Should Prioritize Construct Validity** ([2503.10694](https://arxiv.org/abs/2503.10694);
  Alaa et al., 2025) — argues medical benchmarks should be *empirically* validated, not trusted by
  exam-style fiat. Supports designing convergent/discriminant checks for our conditioning manipulation.
- **✓ Shortcut Learning in Deep Neural Networks** ([2004.07780](https://arxiv.org/abs/2004.07780);
  Geirhos et al., Nat. Mach. Intell.'20) — the foundational "intended vs. unintended decision rule"
  vocabulary. Lets us say the engineered record *could* become a shortcut, then show our controls break it.
- **✓ Leaving the Barn Door Open: Simple Features Predict LLM Benchmark Answers** ([2410.11672](https://arxiv.org/abs/2410.11672);
  Pacchiardi et al., 2024) — cheap n-gram classifiers score high on modern benchmarks, i.e. surface
  features leak answers. The template for a **record-only / surface-cue probe**: if a weak model seeing
  *only* the injected record scores well, the relevance is doing the work.
- **✓ Annotation Artifacts in NLI** ([1803.02324](https://arxiv.org/abs/1803.02324); Gururangan et al.,
  NAACL'18) — a *hypothesis-only* model hits ~67% on SNLI: the construction process injects
  label-predictive artifacts. Near-perfect analogy; the **partial-input baseline** is the direct
  methodological transplant.
- **✓ Learning the Difference that Makes a Difference (counterfactually-augmented data)** ([1909.12434](https://arxiv.org/abs/1909.12434);
  Kaushik et al., ICLR'20) — minimal edits that flip to a counterfactual target reduce reliance on
  spurious cues. The principled version of "generate data toward a target answer," and the basis of
  our **counterfactual-record control** (records pointing to a *different/no* answer).
- **✓ A Framework for Understanding Label Leakage in ML for Health Care** (Davis et al., JAMIA'23) —
  distinguishes *appropriate* vs. *inappropriate* information flow by cadence/perspective/applicability.
  The exact tool to argue our injected data is "in-perspective" (what a clinician would plausibly have)
  rather than leaking the rubric's answer.
- **✓ What Has Been Lost with Synthetic Evaluation?** ([2505.22830](https://arxiv.org/abs/2505.22830);
  Gill, Ravichander & Marasović, 2025) — LLM-generated benchmarks are often *valid but easier*,
  inflating scores. A direct caution to report difficulty/discrimination and not let conditioning make
  the task trivially easy.
- **The Clever Hans Mirage (spurious-correlation survey)** ([2402.12715](https://arxiv.org/abs/2402.12715))
  and **CEval** ([2404.17475](https://arxiv.org/abs/2404.17475)) [both ✓ in sweep] — a menu of
  detection/mitigation controls and counterfactual-quality metrics (validity, minimality, fluency) to
  characterize how tightly engineered our records are.

### B3 — Missing/noisy data, abstention & graceful degradation *(vision §4 N2)*

*"Correct use" is a* policy *over data states — ask when absent, use when present, reconcile/flag
when conflicting — not a single answer. This bucket supplies the metrics for the degradation curve.*

- **✓ MediQ** ([2406.00922](https://arxiv.org/abs/2406.00922); Li et al., NeurIPS'24) — recasts
  medical QA as an interactive Patient↔Expert loop where the model must abstain and ask under
  incomplete records; *naive* prompting-to-ask hurts, confidence-gated asking helps (+22.3%). The
  canonical "ASK when data absent" instantiation and a method to reuse for state (1)/(2).
- **✓ AbstentionBench** ([2506.09038](https://arxiv.org/abs/2506.09038); Meta/FAIR, 2025) — 20
  LLMs × 20 datasets across 6 scenarios incl. **underspecification** and **stale data**; abstention
  is unsolved and reasoning-tuning *degrades* it ~24%. Its scenarios map onto our states; abstention
  rate/recall is a reusable curve axis.
- **✓ Know Your Limits: A Survey of Abstention in LLMs** ([2407.18418](https://arxiv.org/abs/2407.18418);
  2024) — organizes abstention along query/model/values axes; supplies metric definitions
  (over-/under-abstention) for the ASK-vs-USE policy.
- **✓ CLAMBER** ([2405.12063](https://arxiv.org/abs/2405.12063); ACL'24) — ~12K-example benchmark;
  LLMs poorly recognize *when* a query is ambiguous and clarify badly. A clarification-question-quality
  metric for state (1)/(2).
- **Q4Dx — goal-directed diagnostic questioning** (Sci. Reports'26) [lead] — cases instantiated at
  **100% / 80% / 50% symptom exposure** with metrics ZDA / MQD (mean questions to dx) / ISE (inquiry
  efficiency). Essentially a *graceful-degradation curve already built* across information levels — a
  strong template for our per-model curve. (Verify the venue/ID before citing.)
- **✓ RAG with Conflicting Evidence (MADAM-RAG / RAMDocs)** ([2504.13079](https://arxiv.org/abs/2504.13079);
  2025) — multi-agent debate over conflicting/noisy/misinformation evidence; +11–16% but a large gap
  remains under imbalance. The core RECONCILE method + dataset for state (3).
- **✓ DriftMedQA** ([2505.07968](https://arxiv.org/abs/2505.07968); 2025) — 4,290 scenarios on
  evolving/conflicting clinical guidelines; RAG + preference tuning most robust. A stale-and-conflicting
  metric source for state (3).
- **✓ Aligning Probabilistic Beliefs under Informative Missingness** ([2512.00479](https://arxiv.org/abs/2512.00479);
  2025) — LLMs don't natively exploit the fact that a *missing field is itself signal* without prompt
  intervention. Sharpens state (2): absence is informative, not just "less data."
- **✓ Performance of LLMs Under Input Variability in Healthcare** (Joshi et al., JMIR AI'26) — typos /
  homophones / **redactions** across 3 LLMs × 3 tasks; robust to surface noise but **redactions (≈
  missing fields) are most damaging**. A noise-type-stratified shape for the curve.
- **✓ Uncertainty Quantification & Calibration in LLMs: A Survey** ([2503.15850](https://arxiv.org/abs/2503.15850))
  and **✓ Medical Hallucinations in Foundation Models** ([2503.05777](https://arxiv.org/abs/2503.05777))
  — calibration and hallucination-rate as cross-cutting curve metrics, esp. for fabrication-instead-of-asking
  in states (1)/(2).

### B4 — Relevance under a full record / long context *(vision §4 N3)*

*Real systems hand the model the* whole *record; the capability shifts from "use the data" to
*selection*: find the decision-relevant fields amid distractors, without over-trusting an
irrelevant value or losing the key one. Includes the context-interface axis (raw dump vs. summary
vs. retrieval).*

- **✓ Lost in the Middle** ([2307.03172](https://arxiv.org/abs/2307.03172); Liu et al., TACL'24) —
  U-shaped curve: accuracy is high when the relevant item is at the start/end and degrades when
  buried; worse as context grows. The multi-doc-QA template (1 gold + N distractors, varying position)
  is exactly our design; position is a confound we must control.
- **✓ LLMs Can Be Easily Distracted by Irrelevant Context** ([2302.00093](https://arxiv.org/abs/2302.00093);
  Shi et al., ICML'23) — GSM-IC injects irrelevant sentences; accuracy drops sharply, partly recoverable
  via "ignore irrelevant information" + self-consistency. The canonical distractor-induced-error method
  and baselines.
- **✓ RULER** ([2404.06654](https://arxiv.org/abs/2404.06654); COLM'24) — multi-needle / multi-hop /
  aggregation NIAH; "32K" models often fail at 32K. The way to parametrically scale haystack length and
  needle count; the length-vs-accuracy curve is our headline plot.
- **✓ RGB — Benchmarking LLMs in RAG** ([2309.01431](https://arxiv.org/abs/2309.01431); AAAI'24) —
  four abilities: noise robustness, **negative rejection**, information integration, counterfactual
  robustness. "Negative rejection" ≈ not over-trusting an irrelevant value; metrics liftable wholesale
  for the retrieval-vs-raw-dump arm.
- **✓ MedDistractQA** ([2504.01201](https://arxiv.org/abs/2504.01201); 2025) — USMLE-style questions
  seeded with clinical-sounding distractions cut accuracy up to **17.9 pp**, and **RAG did not fix it**
  (sometimes added confounders). The closest clinical analogue — but distractors live *in the question*,
  not in a long surrounding record. A key precedent and a result to re-probe under the full-record setting.
- **✓ MedOdyssey** ([2406.15019](https://arxiv.org/abs/2406.15019); 2024) — first medical long-context
  benchmark (4K→200K, medical NIAH + tasks). The nearest existing *clinical long-context* benchmark — but
  not built around longitudinal-record distractor selection or the interface axis, leaving our contribution open.
- **✓ RAG vs. Long-Context for Clinical Reasoning over EHRs** ([2508.14817](https://arxiv.org/abs/2508.14817);
  2025) — on real EHRs, RAG matches/approaches full-context accuracy at far fewer tokens. The single most
  on-axis paper for our interface comparison; we extend it with the *structured-summary* interface and
  distractor-induced-error isolation.
- **✓ Long-Context Comprehension for Medical QA** ([2510.18691](https://arxiv.org/abs/2510.18691); 2025)
  — studies LLM comprehension over long clinical QA with "content of varying size and relevance"
  (≈ our distractor-volume knob); cautions that memorization can inflate hit rate. Confirms the niche is
  active and open.
- **✓ IE from Clinical Notes: Are We Ready to Switch to LLMs?** ([2411.10020](https://arxiv.org/abs/2411.10020);
  2024/25) — instruction-tuned LLaMA-3-70B beats BioBERT on clinical NER/RE but ~28× slower. Defines the
  clinical-IE baseline + entity-F1 metric for "did the model surface the decision-relevant field."
- **Leads:** **CliCARE** ([2507.22533](https://arxiv.org/abs/2507.22533)) — longitudinal cancer-EHR
  grounding; **ER-Reason** ([2505.22919](https://arxiv.org/abs/2505.22919)) — ER reasoning over full
  records. Both [lead]; promising longitudinal-record precedents.

### B5 — Numeric & wearable time-series grounding *(vision §4 N4)*

*The hardest, most Meta-relevant axis: can a model read sensor/lab* numbers and trends *—
units, noise, downsampling — not just described symptoms? Heavily benchmarked already, and
partly* future work *for us because Synthea lacks high-frequency streams.*

- **✓ PH-LLM** ([2406.06474](https://arxiv.org/abs/2406.06474); Google, Nature Medicine'25) — wearable
  sleep/fitness reasoning; the textual-vs-multimodal *encoding* contrast directly maps to our
  serialization axis. Primary wearable baseline (also B1).
- **✓ Health-LLM** ([2401.06866](https://arxiv.org/abs/2401.06866); CHIL'24) — 12 LLMs × 10 consumer-health
  tasks; fine-tuned HealthAlpaca matches GPT-4/Gemini on 8/10, and health-knowledge context adds up to
  +23.8%. Baseline for numeric-claim accuracy from HR/sleep/steps.
- **✓ PHIA (wearable-data agent)** ([2406.06464](https://arxiv.org/abs/2406.06464); Google, Nat. Commun.) —
  multi-step reasoning with **code generation + retrieval**; 84% on objective numerical questions. The
  strongest evidence that **tool-use/code-execution** wins for numeric wearable questions.
- **✓ OpenTSLM** ([2510.02410](https://arxiv.org/abs/2510.02410); 2025) — time series as a *native
  modality* (SoftPrompt / cross-attention); vastly beats text-serialized numbers (e.g. 69.9% vs 9.1%
  sleep staging). The realistic *ceiling* architecture if we ever get high-frequency streams.
- **✓ HEARTS** ([2603.06638](https://arxiv.org/abs/2603.06638); ICML'26) — 16 datasets / 12 domains / 110
  tasks; LLMs substantially underperform specialists, lean on heuristics, fail multi-step temporal
  reasoning — "scaling alone is insufficient." The broadest health-time-series benchmark; the SOTA we'd
  position against.
- **✓ LMs Still Struggle to Zero-shot Reason about Time Series** ([2404.11757](https://arxiv.org/abs/2404.11757);
  Merrill et al., EMNLP'24 Findings) — near-random on reasoning, up to 30 pts below humans; good
  forecasting ≠ reasoning. Core motivation.
- **✓ TimeSeriesExam** ([2410.14752](https://arxiv.org/abs/2410.14752); NeurIPS'24) — IRT-calibrated MCQs
  incl. **noise understanding** and anomaly; all models fail on causality. Procedural generation reusable
  for numeric-claim items at scale.
- **✓ LLMTime** ([2310.07820](https://arxiv.org/abs/2310.07820); NeurIPS'23) — digit-string serialization
  forecasting; critically, **GPT-4 can do worse than GPT-3 purely from how it tokenizes numbers**. Decisive
  evidence that *encoding choice changes accuracy* — validates our raw-vs-summary-vs-feature comparison.
- **✓ A Picture is Worth a Thousand Numbers (VL-Time)** ([2411.06018](https://arxiv.org/abs/2411.06018)) —
  plotting the series as an *image* for a multimodal LLM gives ~140% improvement at ~99% fewer tokens. A
  serialization condition to add (visualization vs numeric text).
- **✓ NumericBench** ([2502.11075](https://arxiv.org/abs/2502.11075); ACL'25) — six numerical abilities;
  GPT-4/DeepSeek lean on surface statistics not magnitude. Motivates numeric-claim-accuracy testing.
- **✓ Program of Thoughts** ([2211.12588](https://arxiv.org/abs/2211.12588); TMLR'23) — offload computation
  to a code interpreter; ~12% over CoT. The canonical method for our code-execution arm (pairs with PHIA).

### B6 — Synthetic & counterfactual clinical data generation (the method engine)

*The engine behind "instantiate a record to spec." Strong precedent for the method — and the
strongest realism caveats we must report.*

- **✓ Synthea** (Walonoski et al., JAMIA'18; [DOI:10.1093/jamia/ocx079](https://doi.org/10.1093/jamia/ocx079))
  — open-source engine simulating whole synthetic patient lives from disease-progression + standard-of-care
  modules; privacy-risk-free at scale. *The* method engine; the module/guideline design is exactly our
  "generate to spec."
- **✓ Synthea validity study** (Chen et al., BMC Med Inform Decis Mak'19;
  [DOI:10.1186/s12911-019-0793-0](https://doi.org/10.1186/s12911-019-0793-0)) — Synthea matches
  demographics and care-process probabilities but **badly misestimates outcomes/complications** (e.g. COPD
  30-day mortality 0.7% vs 7–8%; BP control 0% vs ~70%), because it follows idealized guideline care. The
  single most important **threat-to-validity** citation when outcomes are decision-relevant.
- **✓ Generating Synthetic EHR Data — scoping review + benchmark** ([2411.04281](https://arxiv.org/abs/2411.04281);
  2024) — 48 methods on MIMIC; **rule-based generators (Synthea) win on privacy but lag on downstream
  utility/correlation fidelity**. The best landscape+caveat citation.
- **✓ HiSGT (hierarchy/semantics-guided Transformer)** ([2502.20719](https://arxiv.org/abs/2502.20719);
  2025) — generates records **conditioned on phenotype labels first, then codes**, preserving the
  feature–label joint. Direct precedent for *controllable generation to spec*.
- **✓ Synthetic Medical Records with Commercial LLMs** ([2504.14657](https://arxiv.org/abs/2504.14657);
  UCLA'25) — plausible at ~10 features (AUC 0.91+) but **fails to preserve distributions/correlations as
  dimensionality grows (83 features)**, with lab values badly mismatched and rising membership-inference
  risk. The caveat if we LLM-fill fields rather than using Synthea.
- **✓ PatientSim** ([2505.17818](https://arxiv.org/abs/2505.17818); 2025) — 24-item patient profiles
  from **MIMIC-IV** + persona conditioning; clinician quality 3.89/4. A higher-fidelity, EHR-grounded
  alternative for instantiated patients. (See also **✓ AIPatient** [2409.18924] — KG-grounded, 94% QA;
  **✓ AgentClinic** patient agents [2405.07960].)
- **✓ Polyjuice** ([2101.00288](https://arxiv.org/abs/2101.00288); ACL-IJCNLP'21) — controllable
  counterfactual generator used to *evaluate* models. The methodological anchor for "counterfactual
  instantiation" as an evaluation tool, not just training augmentation.
- **✓ MedAgentBench as synthetic-eval precedent** ([2501.14654](https://arxiv.org/abs/2501.14654)) —
  FHIR-compliant virtual EHR of 100 profiles + physician tasks: synthetic/structured records used to build
  an *evaluation* benchmark (not training data). Direct design precedent for Direction B (also B1).
- **Leveraging Generative AI for Synthea modules** ([2507.21123](https://arxiv.org/abs/2507.21123); 2025)
  [✓ in sweep] — LLMs author/extend Synthea disease modules to widen coverage. Useful if our vignettes need
  conditions Synthea doesn't ship.

---

## §3. Implications — the gap and an actionable plan

*Recommendations only. Per project convention the idea doc [`../vision.md`](../vision.md) is left
as-is; this section is where the "this may change the idea" reading lives.*

### 3.1 Why mutate an existing benchmark rather than build a new one

The first objection to the gap below is not "is it open?" but "*so what — why not just build a
new, better benchmark on real data, instead of mutating HealthBench?*" The answer is that the two
approaches answer **different questions**, and only mutation answers ours. A new real-data
benchmark is an *observational* instrument — "how well do models do on real data?"; mutation is a
*controlled, counterfactual* one — "*what specifically breaks when data is added, and why?*" The
project's entire value sits in the second question. Six reasons make mutation the correct design,
not a shortcut.

1. **The contribution is a *delta*, and a delta needs a paired design.** Every headline claim is
   comparative: *X% of criteria are data-dependent*; *the static rubric penalizes data use by N
   points*; *model M falls from rank 3 to rank 6 once data is present*. Each is a statement about
   `R`-under-no-data vs. `R`-under-data, or `R` vs. `R′` — it is **undefined without the original
   `(V, R)` as the counterfactual baseline.** A fresh real-data benchmark has no "before": it can
   report an absolute level ("model scores 60%") but never the *mis-attribution* ("the data-blind
   assumption scored this +30pp wrong"). The delta **is** the finding, and mutation is the only
   design that produces it. This is exactly counterfactually-augmented data (Kaushik et al.,
   ICLR'20; B2) lifted from labels to rubrics: minimally edit one factor, hold everything else
   fixed, study *the difference that makes a difference*.

2. **Identification and statistical power — the strongest, most quantitative point.** Comparing a
   new benchmark's scores to HealthBench's confounds the data effect with topic, difficulty,
   phrasing, and rubric-author differences: any gap is uninterpretable. There is a sharper,
   project-specific version. *Decomposing Physician Disagreement* (Direction A §A4,
   [2602.22758](https://arxiv.org/abs/2602.22758)) finds **~82% of HealthBench label variance is
   case-level residual** and only ~16% is rubric identity. A *between-benchmark* comparison is
   therefore swamped by case-level noise — the data effect would sit below the detection floor. A
   *within-item* mutation **differences that dominant term out**: same case, same conversation,
   only the data state varies. So the paired design is not merely convenient; given the noise
   structure it is close to *necessary* to detect the effect at all — a power argument we can state
   numerically in the paper.

3. **Inheriting expert gold — validated quality *and* atomic granularity.** HealthBench is 48,562
   conversation-specific weighted criteria from 262 physicians: peer-reviewed, on hard emergency
   and context-seeking cases — precisely where data-conditioning bites hardest. Two consequences:
   - *Validated quality is cheap to inherit, expensive to reproduce.* The realistic alternative to
     mutation is **not** "a new benchmark with equally good rubrics" — the project has **no
     physician access right now** (a resolved constraint, vision §12). So the honest alternative is
     a new benchmark with *worse, un-validated* rubrics. Mutation stands on validated gold and
     re-validates only **the delta** — the handful of criteria that changed per item, not all 48k.
     That collapse of the physician-validation surface (vision C3) is what makes the project
     feasible, and is itself part of the contribution.
   - *Atomic granularity makes the mutation operation well-defined.* Because criteria are explicit
     and atomic ("ask about X", "+pts for recommending Y"), one can mechanically identify *which*
     criteria the record makes moot and *how* it changes each (moot / induced / urgency). A
     holistic or coarse rubric has **no seam to mutate** — the operation could not even be defined.
     The expert rubric's specificity is what makes mutation auditable and automatable.

4. **Comparability and the rank-shift result.** Reusing the same items and the same model suite
   keeps our data-grounded scores **directly comparable to the published HealthBench leaderboard**.
   "Model M ranks 3rd text-only but 6th once data is present" is a statement about the *same*
   benchmark — impossible from an apples-to-oranges new dataset, and itself a headline only the
   anchored design can produce.

5. **Outcomes only mutation can yield** (impossible by construction in a fresh real-data benchmark):
   - the **mis-scoring quantity** — how wrong the static rubric is — needs the original rubric as
     reference;
   - the **ask→use behavioral transition** and **"right for the wrong reason"** detection (an answer
     scored well by *asking* in text-only, then mishandling the same data once present) — needs the
     *same item* across both regimes (B3);
   - **known ground-truth relevance**: synthesizing the record *to spec* against the rubric means we
     *know* which fields are decision-relevant, which is what lets us cleanly mutate the rubric,
     build the B4 distractor controls, and run the monotonicity / hidden-context test. A real record
     carries *uncontrolled* relevance and forfeits that leverage;
   - the **full data-state spectrum** (B3): a static real-data benchmark is only the "(4) present,
     clean" corner — mutation builds the *same case across all four states* and scores the
     conditional policy.

6. **The honest steelman — the real-data benchmark is downstream, not a rival.** The mutation design
   is the *controlled instrument*; it tells you what to measure and what breaks. The naturalistic
   real-cohort benchmark — the project's own **Phase 5** (vision §9) — is the *field study* that
   establishes external validity, and it inherits the failure taxonomy and the validated mutation
   operator the instrument produced. You calibrate the instrument first, then run the field study;
   you do not start with the uncontrolled one. The synthetic-data limitation (B2/N1) is *why* this
   is framed as a controlled diagnostic plus future real-data validation — sequenced and
   complementary, not a concession.

**In one sentence (for the draft):** *we mutate rather than rebuild because the quantity of
interest is a counterfactual delta — how the ideal answer, the rubric, and the model ranking change
when data appears — which is identifiable only by holding the expert-validated task fixed and
varying the data state; a fresh benchmark discards the counterfactual, the validated gold, and the
leaderboard comparability, and (with ~82% of HealthBench variance at the case level) lacks the
power to detect the effect at all.*

### 3.2 The gap, stated precisely

The user's prior is confirmed and sharpened. Three concentric circles, outer-to-inner:

1. **"Evaluate a health LLM with the patient's own structured data" — crowded** (B1a–c:
   MedAlign, MedAgentBench, AgentClinic, EHRSHOT, EHRNoteQA, PH-LLM). Not a contribution on its own.
2. **"Auto-generate instance-specific medical rubrics" — crowding fast** (B1d + Direction A
   §A2/§A4: MedDialogRubrics, Automated Medical-Dialogue Rubrics, Health-SCORE, Adaptive Precise
   Boolean rubrics). The criteria adapt to the *task / guideline*, generated from the conversation
   or a synthetic case.
3. **"Mutate a given item's rubric *because a real record was injected*" — open.** No paper in
   this corpus takes one fixed task, supplies the patient's structured data, and changes the
   *scoring criteria*: existing criteria become **moot** (the model shouldn't ask for what's on
   file), new **data-grounded** criteria appear (correctly read the value, flag the documented
   allergy), and **urgency flips** (an abnormal value → emergency referral). The phase-2 PoC
   already prototypes exactly this ([phase2-poc.md](../../experiments/data-grounded-healthbench/reports/phase2-poc.md):
   a −62pp swing on the sharp case). **This is the A∩B white space and the defensible novelty.**

Differentiate sharply from the three nearest neighbors, because reviewers will reach for them:
- **vs. PH-LLM** — conditions the *input* on the user's data but applies *fixed* expert rubrics;
  we change the rubric itself.
- **vs. Adaptive Precise Boolean rubrics** — improves rubric *format* (boolean decomposition); we
  change rubric *content* as a function of the record.
- **vs. Health-SCORE / MedDialogRubrics** — generate per-case rubrics from the task/guidelines/synthetic
  cases; we *re-derive an existing physician rubric* against an *injected real record* and measure how
  the original mis-scores data-aware behavior.

### 3.3 Manage two real threats up front

- **Engineered relevance (B2).** Because the record is synthesized from the query+rubric, the trivial
  objection is leakage-by-construction. The literature gives a clean defense kit: **(1)** a **record-only /
  partial-input baseline** (Gururangan'18; Pacchiardi'24) — if a weak model seeing only the record scores
  high, relevance is carrying the task; **(2)** **counterfactual records** (Kaushik'20; Polyjuice) pointing
  to a *different/no* answer — performance must track the *content*, not mere data presence; **(3)**
  **content-corruption ablations** (Geirhos'20; Clever-Hans survey) — the gain must survive cue perturbation
  and collapse when the *relevant* value is corrupted; **(4)** the **label-leakage-in-healthcare** frame
  (Davis, JAMIA'23) to argue the data is "in-perspective" (a clinician would have it), not answer-leaking;
  **(5)** a **difficulty/realism audit** (Gill'25; Synthea validity study) so the conditioning isn't merely
  making the task easy. The "hidden-context / monotonicity" test in vision §4 (better data ⇒ higher score)
  is the positive-control complement.
- **Synthea outcome-unrealism (B6).** Synthea is faithful on demographics and meds/labs/vitals but
  **unrealistic on outcomes/complications** (Chen'19). Keep decision-relevant fields to the well-modeled
  categories (meds, allergies, labs, vitals, problem list — which is where our enrichability already
  concentrates), and explicitly disclaim outcome realism. LLM-filling extra fields degrades correlation
  fidelity (Lin'25), so prefer rule-based generation for the structured core.

### 3.4 Actionable plan (what to run, in order)

The plan reuses the existing phase structure ([vision §9](../vision.md)) and slots each study against
its literature, leading with the cleanest open claims and the studies runnable on Synthea *now*.

1. **Lead study — data-conditioned rubric mutation, validated by score/rank impact (A∩B).** Scale the
   phase-2 PoC: for N HealthBench items, derive R′ from an injected Synthea record and measure how the
   *original* R mis-scores the data-aware answer (the −62pp mechanism) and how R′ realigns it. Validate R′
   with the proxy ensemble now; physician round later (vision C3). **Reuse the Direction-A rank-preservation
   yardstick** (Kendall τ + weight-perturbation, Direction A §A5) to ask whether the *mutation* preserves
   the *intended* ranking. This is the headline contribution; differentiate per §3.2.

2. **Behavioral study — competence as a policy over data states (B3, the cleanest open framing).** Build the
   *same case across the four states* (no data / relevant field missing / present-but-noisy / present-clean),
   score each against a state-appropriate rubric, and plot a **graceful-degradation curve** per model. Reuse
   off-the-shelf metrics: abstention rate (AbstentionBench, Know-Your-Limits), clarification quality + MQD/ISE
   (CLAMBER, MediQ, Q4Dx), calibration + hallucination rate (UQ survey, Medical Hallucinations), conflict
   resolution (RAMDocs, DriftMedQA). This is fully synthesizable on Synthea and turns "the score drops" into a
   policy result.

3. **Validity backbone — run the B2 control suite alongside studies 1–2** (record-only baseline, counterfactual
   records, content-corruption, monotonicity). Without these the lead study is dismissible as leakage; with
   them it is evidence of genuine data-use capability. Treat this as non-optional, not a robustness appendix.

4. **Second study — clinical full-record distractor + context-interface axis (B4).** Hold the relevant fields
   fixed; vary surrounding irrelevant record volume (k distractors → full history) and the interface (raw dump
   vs. structured summary vs. retrieval). Reuse the multi-doc-QA + needle-position design (Lost-in-the-Middle),
   multi-needle scaling (RULER), RGB's negative-rejection/noise metrics, MedDistractQA's pp-drop, and EHRNoteQA
   gold. The gap is real: **no clinical benchmark combines full record + controlled distractors + interface
   axis** — the closest are general-domain or partial clinical slices.

5. **Future / gated — numeric & wearable time-series (B5).** Heavily benchmarked already (HEARTS, PH-LLM,
   OpenTSLM) and **blocked on real high-frequency streams Synthea cannot supply.** Near-term, run only the
   numeracy/trend portion on **lab-value trends and low-frequency vitals** Synthea does expose, and test the
   serialization (raw vs. summary vs. feature; LLMTime/VL-Time findings) and **tool-use/code-execution** arm
   (PHIA, PoT). The high-frequency sensor axis is explicit future work contingent on a real wearable dataset.

**One-line takeaway.** Don't pitch "evaluate health LLMs with data" or "auto-generate medical rubrics"
(both crowded). Pitch **data-conditioned rubric *mutation*** — measuring how a static physician rubric
mis-scores correct data use, with a rank/score-impact metric and a leakage-control suite — and frame the
behavioral result as a **policy over data states**. Both are open, both run on Synthea now, and both sit
exactly on the A∩B intersection the project was built around.

---

## §4. Key papers (verified)

Highest-relevance works, each opened and confirmed this session.

| Paper | arXiv / DOI | One-line relevance | Tag |
|---|---|---|---|
| PH-LLM (Personal Health LLM) | [2406.06474](https://arxiv.org/abs/2406.06474) | Wearable-conditioned eval with **fixed** expert rubrics | closest competitor (input-conditioned) |
| Adaptive Precise Boolean rubrics | [2503.23339](https://arxiv.org/abs/2503.23339) | Boolean-decomposed scalable health rubrics; **not** data-mutating | near-neighbor (rubric format) |
| Health-SCORE | [2601.18706](https://arxiv.org/abs/2601.18706) | Scalable rubric generation; **no** record-conditioned selection | near-neighbor (generation) |
| MedAgentBench | [2501.14654](https://arxiv.org/abs/2501.14654) | Live FHIR EHR agent tasks; conditions task, not rubric | competitor (input/agentic) |
| MedAlign | [2308.14089](https://arxiv.org/abs/2308.14089) | 983 instructions over real longitudinal EHRs; ranked vs reference | competitor (input) |
| Measuring What Matters (construct validity) | [2511.04703](https://arxiv.org/abs/2511.04703) | Name & frame the engineered-relevance threat | threat-to-validity |
| Annotation Artifacts in NLI | [1803.02324](https://arxiv.org/abs/1803.02324) | Hypothesis-only baseline exposes construction artifacts | CRITICAL (leakage control) |
| Simple Features Predict Benchmark Answers | [2410.11672](https://arxiv.org/abs/2410.11672) | Record-only / surface-cue probe template | CRITICAL (leakage control) |
| Counterfactually-Augmented Data | [1909.12434](https://arxiv.org/abs/1909.12434) | Target-conditioned generation, made fair via counterfactual controls | method (defense) |
| Label Leakage in ML for Health Care | JAMIA'23 | "In-perspective" vs answer-leaking information flow | framing (fair-vs-cheating) |
| MediQ | [2406.00922](https://arxiv.org/abs/2406.00922) | Interactive ASK-when-absent; naive asking hurts | method (data-state policy) |
| AbstentionBench | [2506.09038](https://arxiv.org/abs/2506.09038) | Abstention unsolved; underspecification + stale-data scenarios | metric source (degradation) |
| Lost in the Middle | [2307.03172](https://arxiv.org/abs/2307.03172) | U-shaped position curve; multi-doc-QA distractor template | method (long-context) |
| MedDistractQA | [2504.01201](https://arxiv.org/abs/2504.01201) | Clinical distractors cut accuracy ≤17.9pp; RAG doesn't fix | closest clinical competitor (B4) |
| RAG vs Long-Context over EHRs | [2508.14817](https://arxiv.org/abs/2508.14817) | RAG ≈ full-context at fewer tokens, on real EHRs | method (interface axis) |
| HEARTS | [2603.06638](https://arxiv.org/abs/2603.06638) | LLMs weak at multi-step health time-series reasoning | competitor / motivation (B5) |
| LLMTime | [2310.07820](https://arxiv.org/abs/2310.07820) | Number tokenization alone changes accuracy | CRITICAL (serialization) |
| PHIA (wearable agent) | [2406.06464](https://arxiv.org/abs/2406.06464) | Code-gen/tool-use wins for numeric wearable questions | method (tool-use) |
| Synthea | JAMIA'18 | The generate-to-spec engine | method (data) |
| Synthea validity study | BMC MIDM'19 | Faithful demographics/process, **unrealistic outcomes** | threat-to-validity (data) |

---

## §5. Status & how to add entries

- **Status:** first full pass for Direction B (2026-06). Buckets B1–B6 populated (B2–B5 ↔ vision §4
  N1–N4); §3 holds the gap + actionable plan; §4 is the verified short-list.
- **Verification:** **✓** entries and everything in §4 were opened against arXiv / the journal page this
  session — most by topic-specific research agents, three closest-competitor papers (2503.23339,
  2601.18706, 2406.06474) **personally re-read** to correct an over-reading in the sweep (neither the
  Google Adaptive-Boolean framework nor Health-SCORE actually conditions/mutates the rubric on injected
  patient data — both are scalable-rubric work; PH-LLM conditions the input but keeps rubrics fixed). The
  correction *widens* the gap in §3. **[lead]** entries are leads from the sweep — open and confirm title,
  authors, and claim before citing in the paper draft under [`../../latex/`](../../latex/).
- **Overlap with Direction A.** Some papers appear in both reviews by design: Health-SCORE,
  MedDialogRubrics, Automated Medical-Dialogue Rubrics, ClinAlign (Direction A §A4), and Construct Validity
  in LLM Benchmarks (§A5). They are the literal A∩B seam — cite once, cross-reference.
- **Adding an entry:** capture citation, 1-line claim, which bucket / RQ (vision §2) it informs, and how we
  use it (motivation / method / baseline / threat). Promote the strongest into the related-work section of
  the paper draft; keep depth there, not here.
