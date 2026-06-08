# How much of HealthBench already contains the user's own data?

**Question.** What fraction of HealthBench's 5,000 conversations *already* include the
patient's own structured health data — a medication they take, lab/test result values,
vital-sign values, an EHR/clinical-record excerpt, or wearable/sensor readings — present
in the conversation itself (vs. the project's premise of *injecting* such data)?

## 1. The paper does not report it
The HealthBench paper reports themes and axes but no "% of conversations containing the
patient's data." The closest is the **health data tasks** theme = **9.5%** (477 examples),
but that is a *task type* (drafting notes, transforming clinical data), not "the patient's
own data values are present," which cuts across all themes. So we measured it.

Reported HealthBench distributions (for reference):
- **Themes:** global health 21.9% · responding under uncertainty 21.4% · expertise-tailored
  communication 18.4% · context seeking 11.9% · emergency referrals 9.6% ·
  health data tasks 9.5% · response depth 7.2%.
- **Axes:** completeness 39% · accuracy 33% · context awareness 16% ·
  communication quality 8% · instruction following 4%.

## 2. Method
Two complementary measurements over the user turns of each conversation:

1. **Regex heuristic, full census (all 5,000).** Lexicon + proximity rules for
   medications (drug name/dose tied to "taking / prescribed / on …"), labs (named analyte
   with a nearby value, or lab units, or a described result), vitals (BP / HR / temp / SpO₂ /
   weight / BMI values), wearables (device or sensor metric), and EHR/record context
   (PMH / problem list / pasted note / ICD / "Vitals:/Meds:/Labs:" blocks). Deliberately does
   **not** count a bare symptom or a drug/condition named only as a *topic*.
   Code: [src/analysis/user_data_scan.py](../src/analysis/user_data_scan.py).
2. **LLM judge on a random sample (n=600), with a 95% CI.** A reproducible random sample is
   judged by an LLM against the same definition, giving an unbiased prevalence and calibrating
   the heuristic's precision/recall. Code:
   [build_eval_sample.py](../src/analysis/build_eval_sample.py) +
   [build_eval_sample2.py](../src/analysis/build_eval_sample2.py) +
   [eval_aggregate.py](../src/analysis/eval_aggregate.py).

Two thresholds are reported:
- **Strict** — concrete record-like data is present (med / lab / vital / wearable / pasted record).
- **Broad** — strict, **or** the user states a specific diagnosis / condition history with no values.

### The LLM judge prompt
Each conversation's user turns were handed to an LLM with a per-category rubric; it returns,
for every conversation, a flag for each category plus the two thresholds. The essence of the
prompt:

> You are a careful clinical-data annotator. For each conversation, decide whether the user's
> message(s) **already contain the patient's own concrete, structured health data**. Set
> `has_structured_data = YES` if any of these categories is present:
> - **medication** — a specific drug the patient *takes / was prescribed* (with name and/or dose,
>   incl. by class or unnamed-but-stated-as-theirs: "lisinopril 20 mg", "on warfarin",
>   "I take a blood pressure pill"). **Not** a drug named only as a *topic* ("metformin side
>   effects", a drug-interaction question).
> - **labs** — lab/test result *values* ("A1c 7.2", "creatinine 1.3 mg/dL"), or a described
>   result ("MRI is normal", "x-ray shows…"). **Not** a guideline threshold that isn't the
>   patient's own value.
> - **vitals** — vital-sign values (BP "146/88", "systolic dropped to 95", HR, temp, SpO₂,
>   weight/BMI as a measured number). A reported "lost 10 lb" complaint is **not** a measured vital.
> - **wearable** — wearable/sensor device or readings (Fitbit / Apple Watch / Oura / CGM /
>   ambulatory monitor; resting HR, HRV, step count, sleep stages).
> - **ehr_record** — a pasted/quoted clinical record or note: PMH list, problem list, med list,
>   progress/discharge note, chief complaint + exam findings, ICD codes, ventilator settings,
>   "Vitals:/Meds:/Labs:" blocks.
>
> Set `has_structured_data = NO` for plain-language symptoms, general/guideline questions, a
> drug/condition named only as a topic, demographics alone, or a request to *write* a note with
> no actual values. Separately set `dx_history_only = YES` if it is NO but the user states a
> specific diagnosis/condition they have with no values. Judge **only what the text contains**;
> a pasted record counts even if a clinician wrote it; non-English text follows the same rules.
> Output one JSON record per conversation: `{has_structured_data, categories[], dx_history_only}`.

`has_structured_data` → **strict**; `has_structured_data OR dx_history_only` → **broad**. The
heuristic uses the same category definitions in regex form (see `user_data_scan.py`), which is
how precision/recall below are computed.

## 3. Result

| Measurement | Strict | Broad |
|---|---|---|
| Regex heuristic (census, all 5,000) | 9.1% | 18.9% |
| **LLM judge (random n=600, 95% CI)** | **16.8%** [14.1–20.0] | **25.0%** [21.7–28.6] |

The n=200 and n=600 LLM reads agree (16.5% → 16.8%), so the estimate is stable.

**Category mix (LLM, share of all conversations):** medication ≈ 8.0% · EHR/record ≈ 6.0% ·
labs ≈ 5.8% · vitals ≈ 3.2% · **wearables ≈ 0%** (0/600 sampled; ≤ ~0.5% upper bound).

**Headline:** roughly **1 in 6 HealthBench conversations** already supplies the patient's own
structured data (≈ 1 in 4 if you also count a stated diagnosis). Almost **none** contain
wearable/sensor data — the modality our project most wants to test.

## 4. Why the heuristic under-counts (and the LLM number is the estimate)
On the sample the heuristic scores **~76% precision but only ~38% recall** — it is a *lower
bound*. Regex cannot catch what the LLM does: drug **classes** ("a blood pressure pill",
"OTC antihistamines"), **non-English** meds/labs ("pilule hormonale", "DFG à 25"),
**ventilator settings**, **narrative clinical notes**, and **paraphrased** values ("systolic
dropped to 95"). Its few false positives were defensible LLM "no" calls (a reported
"lost 10 lb" complaint; guideline *thresholds* that are not the patient's own value).

## 5. Caveats
- Single-model LLM judge (proxy, pre-physician-validation); a few borderline note-format
  cases with no values may slightly inflate "strict."
- "Structured data present" is a definitional line; we report strict vs. broad to bound it.
- Sampling error: ±~3% at n=600. A full LLM census would remove sampling error entirely.

## 6. Relevance to the project
This quantifies the gap the project targets: HealthBench is **overwhelmingly data-blind**
(~83% of conversations carry no concrete patient data; ~100% carry no wearable data), yet the
deployment setting is data-rich. It both **motivates** data-conditioned evaluation and bounds
how many existing items could be enriched from their own text vs. need synthesized records.
