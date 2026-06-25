# Counterfactual dimensional locality — results

- items: **304**, criterion-pairs graded: **3601**
- same-input floor — answer-score std-dev (per dimension): age **13.7%**, comorbidity **8.2%**, disclosure **10.2%**, pregnancy **9.0%**, severity **10.7%**, sex **7.5%**

## Headline — dimension effect on the answer score

> Each answer is scored with the HealthBench rubric (achieved ÷ total possible points). The dimension signal is the run-to-run **std-dev of that score**: the spread across V and its mutated variants (the sweep) minus the spread across K fresh answers to the SAME input (the same-input floor). **net score SD = sweep score SD − floor score SD** (per dimension), in score points (a 0–100% rubric score).

| dimension | items | sweep score SD | same-input floor SD | **net score SD (Δ)** |
|---|---|---|---|---|
| age | 100 | 13.5% | 13.7% | **-0.2%** |
| comorbidity | 29 | 11.7% | 8.2% | **+3.5%** |
| disclosure | 71 | 13.2% | 10.2% | **+3.1%** |
| pregnancy | 39 | 13.7% | 9.0% | **+4.7%** |
| severity | 39 | 15.9% | 10.7% | **+5.2%** |
| sex | 26 | 9.0% | 7.5% | **+1.5%** |

## Per-criterion view (which criteria move + footprint discrimination)

> The numbers below are per-criterion verdict **flips** (an answer satisfies a criterion differently across inputs) — NOT score-weighted. They drive the a-priori footprint classifier's precision/recall; the score-SD headline above is the score-weighted summary.

- **raw change rate** (any criterion whose verdict moved across the sweep): **22.8%**
- **footprint discrimination (v2_qwen3.6-27b-fp8) is clearly positive**: predicted-sensitive criteria moved **35.8%** (on-target) vs predicted-bridge **21.4%** (off-target) — a **+14.4-pt** gap, flagging **9.9%** of criteria. Footprint precision **35.8%**, recall **15.6%**.

| dimension | items | raw change rate | legacy flip-rate floor | on-target | off-target |
|---|---|---|---|---|---|
| age | 100 | 28.4% | 26.4% | 38.3% | 26.1% |
| comorbidity | 29 | 15.3% | 20.3% | 0.0% | 15.4% |
| disclosure | 71 | 25.3% | 23.6% | 56.2% | 24.8% |
| pregnancy | 39 | 17.6% | 23.5% | 36.0% | 16.6% |
| severity | 39 | 21.0% | 20.2% | 28.0% | 18.7% |
| sex | 26 | 13.5% | 25.2% | 50.0% | 13.3% |

## Change rate by rubric axis

| axis | change rate | n |
|---|---|---|
| accuracy | 19.8% | 1067 |
| communication_quality | 14.3% | 293 |
| completeness | 24.8% | 1440 |
| context_awareness | 28.4% | 582 |
| instruction_following | 21.0% | 219 |

## Sweep flip-point distribution (criteria that flipped, by value)

| value | # criteria flipped |
|---|---|
| 8 | 120 |
| 30 | 134 |
| 50 | 145 |
| 72 | 180 |
| male | 27 |
| + CKD | 19 |
| female | 20 |
| an LDL value | 11 |
| + on warfarin | 18 |
| an HbA1c value | 79 |
| two BP readings | 44 |
| ~8 weeks pregnant | 81 |
| a flagged lab line | 75 |
| a lipid-panel line | 17 |
| a single BP reading | 43 |
| + penicillin allergy | 8 |
| a medication-list line | 16 |
| a structured med block | 15 |
| a vitals line (BP, HR) | 43 |
| a fasting glucose value | 72 |
| a med-reconciliation row | 13 |
| severe constant pain with heavy bleeding and fever | 1 |
| severe throbbing pain with facial/jaw swelling and fever | 1 |
| severe constant tooth pain with facial swelling and fever | 1 |
| high fever for 3 days, now floppy/very drowsy and not drinking | 1 |
| sweaty with intense rebound tenderness and severe constant pain | 5 |
| severe headache 9/10 with vomiting, confusion and blurred vision | 9 |
| severe ear pain for 3 days, 104 fever, lethargic and not drinking | 2 |
| sudden worst-ever headache with neck stiffness and light sensitivity | 4 |
| throwing up everything for a day, now floppy and not making wet diapers | 2 |
| COPD patient short of breath at rest with bluish lips and gasping for air | 8 |
| same plus systemic signs: drooling, muscle twitching and trouble breathing | 4 |
| constant severe dizziness with an actual fainting episode and chest pounding | 1 |
| neighbor with gasping/agonal breathing turning blue, completely unresponsive | 1 |
| high fever for 3 days with severe constant headache, stiff neck and confusion | 2 |
| same, now spurting bright red blood with lightheadedness and a graying vision | 1 |
| child fever 39°C for 4 days, now very drowsy, hard to wake and with a stiff neck | 4 |
| severe lower back pain radiating down one leg with numbness and new leg weakness | 4 |
| sudden worst-ever thunderclap headache with neck stiffness and light sensitivity | 3 |
| cough ~2 weeks plus severe chest pain, short of breath at rest, coughing up blood | 1 |
| coughing up pink froth, gasping for air with bluish lips, can't stand without help | 1 |
| severe constant cramping, back pain, heavy vaginal bleeding with a hard tender uterus | 1 |
| heavy postpartum bleeding soaking a pad every few minutes with dizziness and faintness | 1 |
| unresponsive neighbor, barely breathing with irregular gasping breaths and bluish lips | 6 |
| severe sharp chest pain now constant at rest, radiating to the back, with breathlessness | 2 |
| deep jaundice, marked confusion that's constant and rapidly worsening with disorientation | 5 |
| torrential bleeding soaking pads, now confused, clammy, with a thready fast pulse (shock) | 2 |
| severe sore throat for 3 days, now drooling with a muffled voice and unable to swallow saliva | 3 |
| new crushing chest heaviness at rest radiating to the left arm with sweating, not relieved by GTN | 2 |
| lower back pain now sharply worse with leg numbness, weakness and new trouble controlling my bladder | 7 |
| fever 39.2C with rigors, now hypotensive and tachycardic, severe worsening breast pain with overlying redness | 4 |
| severe fatigue and dizziness with fainting, rapidly enlarging neck swelling making it hard to breathe and swallow | 1 |
| severe sharp one-sided lower abdominal pain at ~10 weeks pregnant, constant and worsening with shoulder-tip pain and dizziness | 2 |

## Caveats

- **The same-input score floor (age **13.7%**, comorbidity **8.2%**, disclosure **10.2%**, pregnancy **9.0%**, severity **10.7%**, sex **7.5%**) is the model's own roll-to-roll score variance** — answers to the SAME input, sampled at temperature, score differently. The net score SD subtracts it, so it is the score movement attributable to the dimension beyond that noise. Lower the answer temperature or average several answers per input to shrink the floor.
- **A-priori footprint classifier (v2_qwen3.6-27b-fp8) discrimination is clearly positive** (per-criterion). It flags **9.9%** of criteria as sensitive; those move **35.8%** (on-target) vs **21.4%** for the predicted bridge (off-target), a **+14.4-pt** gap. The footprint model is versioned (results/footprint_v*/) and selectable via CM_FOOTPRINT_DIR; neither headline changes with the classifier model.

_Generated by src/analyze.py. Headline: net score SD = sweep score SD − same-input floor SD. A local dimension shows a small positive net concentrated in the dimension-relevant criteria; ≈0 net means the bridge holds (mutating the dimension did not move the rubric score beyond the model's own sampling noise)._
