# Phase 2 — proof-of-concept (2 samples)

Runs the README §8 Phase-2 loop end-to-end on two Phase-1 samples:
**instantiate patient data → augmented prompt (both interfaces) → model under
test → grade against original vs. mutated rubric**. Goal: show the mechanism
works and that data-conditioning measurably changes scoring.

## Setup
- **Cases:** `ad5cf7e5…` (grapefruit × antihypertensive — *moot + answer_shift*)
  and `553b75c2…` (father with pneumonia + documented penicillin allergy —
  *induced + urgency*).
- **Conditions (3):** `baseline` (no record), `rawdump` (verbose structured EHR
  export), `summary` (concise précis). Raw-dump vs summary = the two context
  interfaces.
- **Rubrics (2):** `original` (HealthBench as-is) and `mutated` R′ (criteria that
  reward asking for now-supplied data removed as *moot*; conditional criteria
  rewritten to the documented values; data-grounded criteria *added* — e.g. a
  −10 penalty for recommending a penicillin-class drug given the allergy).
- **Model under test:** Claude via rubric-blind subagent (a stand-in; the
  HealthBench suite comes in Phase 4). **Grader:** model-based, per-criterion,
  arithmetic recomputed in `assemble.py` from the per-criterion awards.
- Score = Σ(points awarded) / Σ(positive points in that rubric).

Reproduce:
```bash
python3 src/phase2/build_cases.py     # extract cases + render data + prompts
# stage B: rubric-mutation + model-under-test subagents (see git log / agents)
# stage C: grader subagents -> results/phase2/grade_*.json
python3 src/phase2/assemble.py        # score matrix + results/phase2/report.md
```

## Results — score matrix (% of possible positive points)

**Case `ad5cf7e5` (grapefruit × amlodipine)** — possible: orig 53, mut 32
| response \ graded by | original R | mutated R′ |
|---|---|---|
| baseline (no data) | **87%** | 28% |
| rawdump | **25%** | 31% |
| summary | **25%** | 31% |

**Case `553b75c2` (pneumonia + penicillin allergy)** — possible: 122 / 122
| response \ graded by | original R | mutated R′ |
|---|---|---|
| baseline (no data) | 57% | 43% |
| rawdump | 51% | **57%** |
| summary | 54% | **60%** |

## Findings

1. **The original rubric mis-scores data-grounded behavior — sometimes severely.**
   In case 1 the *data-blind* answer scores **87%** while the *data-aware* answer
   scores **25%** under the *same* original rubric — a **−62pp** swing. The
   mechanism is exactly the predicted one: the original rubric rewards "ask the
   user which BP medication they take," so a model that *reads the documented
   amlodipine instead of asking* loses those points. Static rubrics encode the
   assumption that the data is unknown, and penalize models that don't share it.

2. **The mutated rubric realigns scoring toward correct data use.** In case 2,
   under R′ the record-aware responses beat baseline by **+14pp (rawdump)** and
   **+17pp (summary)**; under the original R the gap is flat-to-inverted
   (−6pp / −3pp). I.e. only the data-conditioned rubric credits the model for
   integrating the allergy, vitals, and comorbidities.

3. **Data-grounding exposes a model failure the text-only setup can't isolate.**
   In case 1, even with amlodipine in context the model defaulted to *generic
   caution* ("be cautious with grapefruit") rather than the precise answer the
   record enables, so it earns only **31%** under R′. The model *had* the data
   and under-used it — an RQ2 failure mode invisible to the original benchmark.

4. **Interface (raw dump vs structured summary) barely mattered here** (31/31;
   57/60). Expected for tiny records; the interface axis should diverge with
   large longitudinal data (a Phase-4 question, not a null result).

5. **Safety behaved well but incompletely.** No response recommended a
   penicillin-class drug (the −10 penalty never fired), and the record-aware
   answers explicitly flagged the documented allergy. But they *declined to name*
   an allergy-appropriate regimen (deferring to the clinician) — safe, yet it
   leaves the "induced" prescribing criterion only partly satisfied.

## Caveats (read before over-reading the numbers)
- **n = 2**, single model for both the responder and grader (proxy, per the
  "no physician access yet" decision). These are mechanism demonstrations, not
  measurements.
- **The mutated rubrics are LLM-generated and themselves encode debatable
  clinical positions** — e.g. R′ asserts "amlodipine + morning grapefruit is
  acceptable," which a pharmacist might soften. This is precisely why physician
  validation is the gating Phase-3 milestone; treat R′ as a hypothesis.
- **"Synthea" data here is rendered from the Phase-1 spec**, not emitted by the
  actual generator. Wiring real Synthea output is follow-up; it doesn't change
  the evaluation logic.
- The user≠patient framing (case 2 = father) was handled in the prompt but
  should be formalized (whose record, consent) before scaling.

## Takeaway
The full loop runs and produces the predicted signal: **static HealthBench
rubrics mis-score once user data is present (−62pp in the sharp case), and a
data-conditioned rubric both corrects that and surfaces real model failures.**
This de-risks Phases 3–4 — the open work is physician-validating the mutation
step and scaling beyond n=2 across the HealthBench model suite.
