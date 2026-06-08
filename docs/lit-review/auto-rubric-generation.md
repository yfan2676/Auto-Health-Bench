# Literature review — Direction A: Automatic rubric generation

> **Scope.** The literature behind **Direction A** of [Auto-Health-Bench](../../README.md):
> *what makes a rubric good, and can we generate good ones automatically?* This is the
> companion review to the Direction-A idea doc [`../auto-rubric-generation.md`](../auto-rubric-generation.md).
> Direction B's literature (the N1–N4 buckets on data-grounded evaluation) lives in the
> [lit-review index](README.md); the two meet at *data-conditioned rubric generation* (§A∩B).
>
> **Coverage.** Recent work is prioritized (2024–2026, preprints included); a few
> foundational older works are kept where they anchor the field or directly bear on our idea.
> Last swept **2026-06**.
>
> **Verification legend.** **✓** = citation opened and confirmed against arXiv this session
> (title, authors, date checked). **No mark** = surfaced by the literature sweep but not
> individually re-opened — treat as a lead and verify before any formal citation.

---

## §1. Landscape at a glance

Two years ago "rubric-based evaluation" meant a human wrote a checklist and an LLM (or a
person) graded against it. As of mid-2026 the field has moved fast, and three things are
**largely settled**:

1. **LLMs can auto-generate instance-specific rubrics that work as judges.** Generating the
   grading criteria per item (rather than scoring holistically) improves agreement with
   humans and reduces variance (CheckEval, TICK, BiGGen Bench, CARMO).
2. **Auto-generated rubrics work as RL reward signals**, often better than scalar reward
   models, and this is now a busy training-time research thread (RaR, RLCF, ARES, RRD,
   InfiMed-ORBIT).
3. **This already extends to health.** Multiple Jan–Feb 2026 papers auto-generate medical
   rubrics and validate on HealthBench, several claiming parity with or superiority to
   physician-written rubrics for training (Health-SCORE, RubricHub, ClinAlign, Automated
   Rubrics for Medical Dialogue, MedDialogRubrics).

What is **still open** — and where our idea should live:

- **Validating a generated rubric by *rank preservation*** (does it reproduce the *model
  leaderboard* the human rubric produces?) rather than by downstream-reward performance,
  pairwise judge accuracy, or per-item human correlation. This specific yardstick is
  under-used; the closest work (RubricBench) measures rubric *validity*, not ranking.
- **How much the ranking depends on item *weights* vs. the item *set*** — i.e. is exact
  weighting even load-bearing? Directly the 2026-06 meeting's open question, and barely studied.
- **Data-conditioned rubric generation** (rubrics that adapt to an injected patient record):
  not present anywhere in this corpus — the cleanest white space, and the A∩B intersection.

See [§3 Implications](#3-implications--what-may-need-to-change) for what this means for the idea doc.

---

## §2. Thematic buckets

Direction-A analogue of Direction B's N1–N4. Buckets A1–A7.

### A1 — Rubric / checklist-based evaluation: the paradigm

*Decomposing a judgment into explicit criteria beats holistic scoring; this is the substrate
our generation work sits on.*

- **G-Eval** ([2303.16634](https://arxiv.org/abs/2303.16634)) — GPT-4 + chain-of-thought
  "form-filling": generate explicit evaluation steps, then score. The seed of "let the model
  reason out criteria before judging."
- **FLASK** ([2307.10928](https://arxiv.org/abs/2307.10928)) — decompose holistic scoring into
  12 fine-grained skills with per-skill rubrics; shows fine-grained beats coarse for both
  interpretability and human agreement.
- **Prometheus 1/2** ([2310.08491](https://arxiv.org/abs/2310.08491)) — open evaluator LMs
  trained to score against a *custom rubric + reference*; establishes that rubric-conditioned
  judging is learnable and correlates with humans (~0.9 Pearson). A baseline judge to beat.
- **✓ CheckEval** ([2403.18771](https://arxiv.org/abs/2403.18771); Lee et al., EMNLP'25-era) —
  human picks dimensions, LLM generates binary YES/NO checklists; +0.45 inter-evaluator
  agreement, lower variance. Early proof that LLM-generated checklists rival human ones.
- **✓ BiGGen Bench** ([2406.05761](https://arxiv.org/abs/2406.05761); Kim et al.) —
  **instance-specific** evaluation criteria across 77 tasks / 103 models; shows tailored
  per-instance criteria discriminate better than fixed task-level rubrics. Core evidence that
  our generated rubrics should be per-conversation, exactly like HealthBench's.
- **✓ TICK** ([2410.03608](https://arxiv.org/abs/2410.03608); Cook, Rocktäschel, Foerster,
  Aumiller, Wang) — instruction-specific LLM-generated YES/NO checklists; +6pts exact
  agreement with human preference, and showing the checklist to humans raises *their*
  inter-annotator agreement too. The cleanest "auto-generated checklist helps" result.
- **✓ LLM-Rubric** ([2501.00274](https://arxiv.org/abs/2501.00274); Hashemi, Eisner, Rosset,
  Van Durme, Kedzie; ACL'24) — *calibrated* multidimensional rubric scoring: combine an LLM's
  per-question distributions through a small trained network to predict each human judge's
  rating. Relevant to turning raw rubric scores into calibrated, judge-aware estimates.

### A2 — Automatic rubric / criteria generation: the methods

*The core of Direction A. As of 2026 there are many ways to generate rubrics; the open issue
is how to validate them.*

- **✓ CARMO** ([2410.21545](https://arxiv.org/abs/2410.21545); Gupta et al., ACL'25 Findings) —
  generate context-specific criteria per query before scoring; beats static rubrics and
  reduces reward hacking. Evidence that *dynamic > static* criteria.
- **✓ Auto-Rubric: Learning From Implicit Weights to Explicit Rubrics** ([2510.17314](https://arxiv.org/abs/2510.17314);
  Xie et al.) — training-free induction of an explicit hierarchical rubric from as few as **70
  preference pairs**, via verification-driven refinement + information-theoretic compression;
  SOTA on RewardBench/JudgeBench. **Directly relevant to the weight question** (§A6): the
  compression step *is* an implicit weighting of items by discriminativeness.
- **✓ RRD — Rethinking Rubric Generation** ([2602.05125](https://arxiv.org/abs/2602.05125);
  Shen et al., Meta) — recursive *decompose → filter* cycle to fix the known failure modes of
  auto-rubrics (poor coverage, dimension conflation, redundancy, misaligned preference) with
  correlation-aware weighting; +17.7 on JudgeBench. A taxonomy of what goes wrong + fixes.
- **✓ CDRRM — Contrast-Driven Rubric Generation** ([2603.08035](https://arxiv.org/abs/2603.08035)) —
  contrastive profiling of preference pairs to find the *causal discriminative* factors, then
  synthesize rubrics; SOTA with only 3K samples. "Generate criteria from what actually
  separates good from bad answers."
- **✓ ARES — Automated Rubric Synthesis for Scalable RL** ([2605.23454](https://arxiv.org/abs/2605.23454);
  Li et al.) — turn documents into QA + co-generate question-specific weighted rubrics at
  scale, with validity filters (self-containment, faithfulness, rubric validity).
- **✓ RubricHub** ([2601.08430](https://arxiv.org/abs/2601.08430); Li et al.) — automated
  **coarse-to-fine** rubric dataset (110K) via principle-guided synthesis + multi-model
  aggregation + difficulty evolution; a post-trained Qwen3-14B hits **69.3 on HealthBench**,
  reportedly surpassing GPT-5. Strong evidence auto-rubrics can even *exceed* human ones for
  training. (Validated by downstream performance, **not** rank preservation.)
- **✓ Autorubric — Unifying Rubric-based LLM Evaluation** ([2603.00077](https://arxiv.org/abs/2603.00077);
  Rao & Callison-Burch) — open framework: analytic rubrics (binary/ordinal/nominal), ensemble
  judging, few-shot calibration, **halo-effect mitigation (score each criterion in its own
  call)**, and psychometric reliability metrics (Cohen's κ). A practical design checklist for
  our own rubric evaluation.
- **✓ AdaRubric** ([2603.21362](https://arxiv.org/abs/2603.21362)) — task-adaptive rubrics
  generated from the task description, scored step-by-step with a dimension-aware filter so
  high-scoring dimensions can't mask failures; r≈0.79 human correlation (+0.16 over static).
- **✓ The skeptic — "Are Checklists Really Useful for Automatic Evaluation?"** ([2508.15218](https://arxiv.org/abs/2508.15218);
  Furuhashi et al., EMNLP'25) — across six checklist-generation methods and eight model sizes,
  benefits are **inconsistent** (help pairwise, mixed in direct scoring), and there is **no
  universal best method**. **The reason rank preservation matters:** "it generates" ≠ "it
  works," so we need an independent yardstick.

### A3 — Rubrics as RL reward signals

*A major reason auto-rubric generation is hot: rubrics make good dense rewards for
non-verifiable tasks. Useful framing, and the source of much of the medical work in A4.*

- **✓ Rubrics as Rewards (RaR)** ([2507.17746](https://arxiv.org/abs/2507.17746); Gunjal et al.) —
  extend RLVR beyond verifiable domains using rubric-based rewards; **+31% relative on
  HealthBench** over a Likert-judge baseline. The canonical "rubrics > scalar reward" result.
- **✓ Checklists Are Better Than Reward Models (RLCF)** ([2507.18624](https://arxiv.org/abs/2507.18624);
  Viswanathan et al.) — RL from synthetic instruction-specific checklists (WildChecklists,
  130K) beats reward models for alignment. Shows checklist generation scales.
- **✓ InfiMed-ORBIT** ([2510.15859](https://arxiv.org/abs/2510.15859); Wang et al.) — medical:
  dynamic per-case rubrics (RAG over HealthBench rubrics) as GRPO reward; strong gains on
  medical dialogue with only 2K samples. A direct A∩(medical RL) precedent.
- **Rubric-ARM** ([2602.01511](https://arxiv.org/abs/2602.01511)) — alternating RL that jointly
  optimizes a rubric *generator* and *judge*, treating rubric generation as a latent action.

### A4 — Medical / clinical rubric generation + physician disagreement

*The bucket most likely to force a reframe: this is exactly Direction A applied to health, and
it is crowded as of early 2026.*

- **HealthBench** ([2505.08775](https://arxiv.org/abs/2505.08775); OpenAI) — the anchor:
  5,000 conversations, 262 physicians, 48,562 conversation-specific weighted criteria, plus a
  physician meta-evaluation set. Our reference rubrics and our ground-truth model rankings.
- **✓ Health-SCORE — Scalable Rubrics for Health-LLMs** ([2601.18706](https://arxiv.org/abs/2601.18706);
  Yang et al.) — auto-generates health-LLM rubrics that **"match human-created ones while
  lowering development effort,"** usable as RL reward and in-context guide. **The most direct
  pre-emption of "can we auto-generate good health rubrics?"** (answer: yes).
- **✓ Automated Rubrics for Reliable Evaluation of Medical Dialogue** ([2601.15161](https://arxiv.org/abs/2601.15161);
  Chen, Maiga, Rahmani, Yilmaz) — retrieval-augmented multi-agent generation of
  instance-specific rubrics grounded in clinical evidence; beats GPT-4o on HealthBench. Another
  direct precedent; the RAG + atomic-fact-decomposition pattern is reusable.
- **✓ MedDialogRubrics** ([2601.03023](https://arxiv.org/abs/2601.03023); Gong et al.) —
  5,200 synthetic cases + **60K+ LLM-generated, clinician-refined** rubrics derived from
  evidence-based-medicine guidelines via reject sampling. Shows the "generate-then-clinician-
  refine" loop at scale.
- **✓ ClinAlign / HealthRubrics / HealthPrinciples** ([2602.09653](https://arxiv.org/abs/2602.09653);
  Lyu et al.) — 7,034 physician-verified preference examples where clinicians *refine*
  LLM-drafted rubrics, distilled into 119 reusable principles; a 30B model beats DeepSeek-R1
  and o3 on HealthBench-Hard. The "clinician-in-the-loop refinement" pattern.
- **✓ LiveMedBench** ([2602.10367](https://arxiv.org/abs/2602.10367); Yan et al.) —
  contamination-free medical benchmark that *weekly harvests* real cases and auto-generates
  case-specific rubrics (16,702 criteria, 38 specialties); automated rubric eval beats plain
  LLM-as-judge. Living-benchmark + auto-rubric in one.
- **MedHELM** ([2505.23802](https://arxiv.org/abs/2505.23802); Nature Medicine'25) —
  clinician-validated taxonomy (5 categories / 121 tasks) evaluated with an **LLM-jury**;
  clinician-grounded but coarser than per-conversation rubrics.
- **✓ Decomposing Physician Disagreement in HealthBench** ([2602.22758](https://arxiv.org/abs/2602.22758);
  Borgohain & Mariathas) — **the result that most reframes our premise:** rubric identity
  explains only **~15.8%** of label variance and physician identity ~2.4%, while **~81.8% is
  case-level residual**; disagreement follows an inverted-U with answer quality, and
  *reducible* uncertainty (missing context, ambiguous phrasing) roughly doubles disagreement
  odds while genuine medical ambiguity barely moves it. Implication: the rubric is **not** the
  dominant lever, so "a better rubric" cannot close most of the gap.
- **Clinical inter-rater ceiling** (clinical-NLP annotation studies) — human–human agreement
  on clinical concepts plateaus around **κ ≈ 0.85–0.90**, partly from guideline/task
  under-specification. Sets a structural ceiling on any "agree with the physician" target.

### A5 — What makes a rubric "good" + rank-preservation & meta-evaluation

*The machinery for our success metric. How do you tell a good rubric / good judge from a bad
one, and how stable is a model ranking?*

- **✓ RubricBench — Aligning Model-Generated Rubrics with Human Standards** ([2603.01562](https://arxiv.org/abs/2603.01562);
  Zhang et al.) — **the closest competitor.** 1,147 pairwise comparisons benchmarking
  model-generated vs human-authored rubrics; finds "SOTA models struggle to autonomously
  specify valid evaluation criteria." But it scores rubric *validity directly*, **not** whether
  a generated rubric **preserves the model ranking** — that gap is our opening.
- **✓ RubricEval** ([2603.25133](https://arxiv.org/abs/2603.25133); Pan et al.) — rubric-level
  meta-evaluation benchmark for instruction following; even GPT-4o gets only **~56% on the hard
  subset**. Calibrates how reliable we can expect a rubric-judge to be.
- **✓ JudgeBench** ([2410.12784](https://arxiv.org/abs/2410.12784); Tan et al., ICLR'25) —
  benchmark for LLM judges on objectively-checkable items; enforces position-swap consistency.
  Methodology for testing judge reliability and position-robustness in our pipeline.
- **MT-Bench & Chatbot Arena** ([2306.05685](https://arxiv.org/abs/2306.05685)) — the seminal
  LLM-as-judge meta-evaluation: ~80% judge–human agreement (= human–human), and the canonical
  catalogue of judge biases (position, verbosity, self-preference). Background for any
  agreement target.
- **✓ Measuring What Matters: Construct Validity in LLM Benchmarks** ([2511.04703](https://arxiv.org/abs/2511.04703);
  Bean et al., 42 authors, NeurIPS'25 D&B) — review of 445 benchmarks: are the phenomenon, the
  tasks, and the *scoring metric* actually aligned? A checklist to keep our generated rubrics
  measuring physician-appropriate care, not fluency.
- **Are Emergent Abilities a Mirage?** ([2304.15004](https://arxiv.org/abs/2304.15004);
  Schaeffer et al., NeurIPS'23) — apparent capability jumps are often artifacts of *metric
  choice*. **Direct warning for our metric:** non-linear item weighting / aggregation can
  manufacture or hide ranking gaps; prefer a rank metric robust to monotone transforms.
- **✓ Dropping Just a Handful of Preferences Can Change Top LLM Rankings** ([2508.11847](https://arxiv.org/abs/2508.11847);
  Huang, Shen, Wei, Broderick) — Bradley-Terry rankings are brittle: dropping **0.003%** of
  Chatbot-Arena preferences can flip the top model; expert-curated (MT-Bench) is more robust.
  **Why "preserve the ranking" must be defined with significance + perturbation tests**, not a
  naive point estimate.
- **✓ Noisy but Valid: Robust Statistical Evaluation of LLMs with Imperfect Judges** ([2601.20913](https://arxiv.org/abs/2601.20913);
  Feng et al., ICLR'26) — hypothesis-testing framework with finite-sample guarantees for
  certifying model comparisons under a noisy judge, using a small human-labeled calibration
  set. A principled way to make rank-preservation claims statistically.
- **Psychometrics / IRT for benchmarks** — tinyBenchmarks ([2402.14992](https://arxiv.org/abs/2402.14992))
  and Anchor Points ([2309.08638](https://arxiv.org/abs/2309.08638)) use item difficulty +
  discrimination to rank models from a few high-information items. Reusable for selecting the
  most *discriminative* generated rubric items, and for choosing held-out HealthBench subsets.
- **Metric choice note.** Kendall's τ (fraction of concordant pairs; robust to ties) as the
  primary rank-preservation statistic, Spearman's ρ (more sensitive to large rank shifts) as a
  secondary check — report both.

### A6 — Setting item weights under expert disagreement

*The 2026-06 meeting's open question: how to set relative item scores when experts themselves
disagree. The field has more to offer here than expected — reuse, don't reinvent.*

- **✓ Auto-Rubric implicit weights** ([2510.17314](https://arxiv.org/abs/2510.17314)) — already
  in A2; the information-theoretic compression objective *learns* relative item weight from
  discriminativeness, a concrete answer to "where do the numbers come from."
- **✓ Plank, "The 'Problem' of Human Label Variation"** ([2211.02570](https://arxiv.org/abs/2211.02570);
  EMNLP'22 position paper) — foundational: disagreement is signal, not noise, and should be
  modeled rather than averaged away. Reframes physician disagreement as informative.
- **✓ Beyond Consensus: Perspectivist Modeling of Annotator Disagreement** ([2601.09065](https://arxiv.org/abs/2601.09065);
  Xu & Jurgens) — survey of disagreement-aware NLP: targets, pooling, evaluation. The map for
  representing physician disagreement instead of collapsing it.
- **✓ NUTMEG** ([2507.18890](https://arxiv.org/abs/2507.18890); Ivey, Gauch, Jurgens, EMNLP'25) —
  Bayesian model that uses annotator background to separate noise from *systematic*
  disagreement, beating naive aggregation. Applicable to 262 physicians of differing specialty.
- **✓ DiADEM** ([2604.08425](https://arxiv.org/abs/2604.08425); Shetty et al.) — learns
  per-demographic importance weights for annotator disagreement. Suggests rubric item weights
  could be conditioned on physician attributes (e.g. specialty) rather than global.
- **Bradley-Terry / Plackett-Luce framing** — the standard way to recover latent quality scores
  (and, by extension, item weights) from pairwise/listwise preferences; relevant if we learn
  weights from physician answer-rankings rather than asking for points directly.

### A7 — Automatic benchmark / task generation

*Supports §3 of the idea doc ("generate new tasks at HealthBench quality, data-agnostic").
Mostly general-domain; reusable pipeline patterns.*

- **AutoBencher** ([2407.08351](https://arxiv.org/abs/2407.08351)) — declarative benchmark
  construction; auto-discovers tasks optimizing difficulty/novelty/separability.
- **BenchAgents** ([2410.22584](https://arxiv.org/abs/2410.22584)) — multi-agent
  plan → generate → verify → evaluate pipeline with explicit verification checks
  (clarity, completeness, consistency, feasibility). A reusable scaffold for rubric generation.
- **Auto Evol-Instruct** ([2406.00770](https://arxiv.org/abs/2406.00770); EMNLP'24) — automated
  difficulty/diversity evolution of instruction data; the "control difficulty" lever.
- **MCQG-SRefine** ([2410.13191](https://arxiv.org/abs/2410.13191); NAACL'25) — medical question
  generation with iterative self-critique + difficulty control; a medical-specific
  generate-then-refine pattern.
- **LiveBench** ([2406.19314](https://arxiv.org/abs/2406.19314)) — contamination-free "living"
  benchmark; the temporal-separation principle (cf. LiveMedBench in A4).
- **ArenaBencher** ([2510.08569](https://arxiv.org/abs/2510.08569)) — benchmark evolution via
  multi-model competitive feedback; aggregates across models to avoid overfitting one judge.

---

## §3. Implications — what may need to change

*Recommendations only. Per project decision the idea doc [`../auto-rubric-generation.md`](../auto-rubric-generation.md)
is left as-is; this section is where the "this may change the idea" reading lives.*

1. **"Can we auto-generate good health rubrics at all?" is largely answered — *yes*, as of
   early 2026.** Health-SCORE, RubricHub, ClinAlign, Automated Medical-Dialogue Rubrics, and
   MedDialogRubrics all generate medical rubrics, several validated on HealthBench, some
   claiming parity-or-better than physicians for training. **A contribution framed as
   feasibility ("we can auto-generate rubrics") is already crowded.** The pitch must move from
   *can-we* to a sharper claim.

2. **Our distinct yardstick survives — lean into it.** Nearly everyone validates generated
   rubrics by *downstream RL reward* (RubricHub, ARES, RaR, RLCF, InfiMed-ORBIT), *pairwise
   judge accuracy* (RRD, CDRRM, JudgeBench), or *per-item human correlation* (AdaRubric,
   Health-SCORE). **Rank preservation** — "does the generated rubric reproduce the *model
   leaderboard* the human rubric produces?" — is under-used. RubricBench is the closest, but it
   measures rubric *validity* via pairwise comparison, **not** ranking. Positioning the
   contribution explicitly as *rank-preserving rubric generation* is defensible and largely open.

3. **Define "preserve the ranking" robustly, or the claim is fragile.** Rankings flip under
   tiny perturbations ([2508.11847](https://arxiv.org/abs/2508.11847)) and metric choice can
   manufacture gaps ([2304.15004](https://arxiv.org/abs/2304.15004)). So: Kendall's τ as the
   primary statistic (+ Spearman ρ), significance via a noisy-judge framework
   ([2601.20913](https://arxiv.org/abs/2601.20913)), and — importantly — a **weight-perturbation
   sensitivity test**. That test *is* the meeting's open question made measurable: if the model
   ranking is stable as item weights are jittered, then the *item set* matters and exact weights
   do not, which is itself a publishable result and a strong argument for automation.

4. **The rubric may not be the main lever — manage the claim.** Decomposing Physician
   Disagreement ([2602.22758](https://arxiv.org/abs/2602.22758)) attributes only ~15.8% of label
   variance to rubric identity and ~81.8% to case-level residual. So even a perfect auto-rubric
   cannot close most of the human disagreement; success should be framed as *reproducing the
   ranking / the physician score distribution*, **not** as eliminating disagreement. The same
   paper's "reducible uncertainty" (missing context) finding is a natural bridge to Direction B.

5. **Don't reinvent the weighting machinery.** The "relative scores under expert disagreement"
   open question already has tools: implicit-weight learning via compression
   ([2510.17314](https://arxiv.org/abs/2510.17314)), perspectivist modeling
   ([2601.09065](https://arxiv.org/abs/2601.09065)), and disagreement-from-background models
   (NUTMEG, DiADEM). Reuse these; the novel part is *applying* them to physician rubric weights.

6. **The cleanest remaining white space is A∩B: data-conditioned rubric generation.** Nothing in
   this corpus generates a rubric that **adapts to an injected patient record** — they generate
   rubrics from the conversation/task alone. That is exactly the intersection the project is
   built around (see [`../auto-rubric-generation.md`](../auto-rubric-generation.md) §5 and the
   [phase-2 PoC](../../experiments/data-grounded-healthbench/reports/phase2-poc.md), which already
   prototypes rubric *mutation*). Recommendation: treat text-only rank-preserving generation as
   the *baseline to establish*, and **data-conditioned** rank-preserving generation as the
   *novel contribution*.

**One-line takeaway.** Keep the rank-preservation experiment, but reposition it: the novelty is
no longer "auto-generate health rubrics," it is (a) *validating by rank preservation* with a
weight-sensitivity analysis, and (b) extending that to *data-conditioned* rubrics (A∩B).

---

## §4. Key papers (verified)

Highest-relevance works, each opened and confirmed against arXiv this session.

| Paper | arXiv | One-line relevance | Tag |
|---|---|---|---|
| RubricBench | [2603.01562](https://arxiv.org/abs/2603.01562) | Benchmarks model- vs human-authored rubrics; validity gap, but **not** rank preservation | closest competitor |
| Decomposing Physician Disagreement (HealthBench) | [2602.22758](https://arxiv.org/abs/2602.22758) | Rubric identity ≈15.8% of variance; ≈81.8% case-level | threat to premise |
| Health-SCORE | [2601.18706](https://arxiv.org/abs/2601.18706) | Auto health rubrics "match human-created ones" | threat to premise |
| RubricHub | [2601.08430](https://arxiv.org/abs/2601.08430) | Auto coarse-to-fine rubrics; 69.3 on HealthBench (> GPT-5) | threat to premise |
| Automated Rubrics for Medical Dialogue | [2601.15161](https://arxiv.org/abs/2601.15161) | RAG multi-agent instance rubrics; beats GPT-4o on HealthBench | threat to premise |
| ClinAlign | [2602.09653](https://arxiv.org/abs/2602.09653) | Clinician-refined rubrics + principles; 30B > o3 on HB-Hard | method to reuse |
| Auto-Rubric (implicit→explicit weights) | [2510.17314](https://arxiv.org/abs/2510.17314) | Learns item weights from 70 preference pairs via compression | CRITICAL (weights) |
| Are Checklists Really Useful? | [2508.15218](https://arxiv.org/abs/2508.15218) | No universal best generator; "generate" ≠ "works" | motivates our metric |
| Dropping a Handful of Preferences | [2508.11847](https://arxiv.org/abs/2508.11847) | Rankings flip under 0.003% data drop | CRITICAL (metric design) |
| Noisy but Valid | [2601.20913](https://arxiv.org/abs/2601.20913) | Certify model comparisons under an imperfect judge | CRITICAL (metric design) |
| RubricEval | [2603.25133](https://arxiv.org/abs/2603.25133) | GPT-4o only ~56% on hard rubric-judging | reliability ceiling |
| RRD (Rethinking Rubric Generation) | [2602.05125](https://arxiv.org/abs/2602.05125) | Decompose→filter fixes auto-rubric failure modes | method to reuse |
| Rubrics as Rewards (RaR) | [2507.17746](https://arxiv.org/abs/2507.17746) | Rubric rewards; +31% on HealthBench over Likert | context (RL use) |
| BiGGen Bench | [2406.05761](https://arxiv.org/abs/2406.05761) | Instance-specific criteria > fixed rubrics | method to reuse |
| Beyond Consensus (perspectivist survey) | [2601.09065](https://arxiv.org/abs/2601.09065) | Map for modeling physician disagreement | method to reuse |
| Construct Validity in LLM Benchmarks | [2511.04703](https://arxiv.org/abs/2511.04703) | Keep rubrics measuring care, not fluency | threat to validity |

---

## §5. Status & how to add entries

- **Status:** first full pass for Direction A (2026-06). Buckets A1–A7 populated; §3 holds the
  repositioning recommendations; §4 is the verified short-list.
- **Verification:** the **✓** entries and everything in §4 were opened against arXiv this
  session. Unmarked entries are leads from the search sweep — **open and confirm the title,
  authors, and claim before citing in the paper draft** under [`../../latex/`](../../latex/).
- **Adding an entry:** capture citation, 1-line claim, which bucket / RQ it informs, and how we
  use it (motivation / method / baseline / threat). Promote the strongest into the related-work
  section of the paper draft; keep depth there, not here.
