#!/usr/bin/env python3
"""Estimate what % of HealthBench conversations ALREADY contain the user's own
structured health data (EHR / medications / labs / vitals / wearables).

The paper does not report this (closest is the "health data tasks" theme = 9.5%,
but that is a task type, not "the patient's data is present"). So we parse.

We scan only USER turns (the patient/clinician-supplied content) and detect
concrete, record-like data values, deliberately NOT counting a bare symptom or
diagnosis ("I have a headache", "I was diagnosed with X") as "structured data".

Output (gitignored): data/derived/user_data_scan.jsonl  (per-example flags+hits)
Console: strict %, broad %, and a per-category breakdown.

NOTE: heuristic/regex measure -> approximate. Calibrate against an LLM judge on a
random sample (see user_data_eval_sample.py) before quoting as final.
"""
import json
import re
from collections import Counter
from pathlib import Path

SRC = Path("data/derived/index.jsonl")
OUT = Path("data/derived/user_data_scan.jsonl")

# ---- lexicons ------------------------------------------------------------
# common drug names (lowercase, word-boundary matched)
DRUGS = r"""
metformin|lisinopril|levothyroxine|atorvastatin|simvastatin|rosuvastatin|amlodipine|
metoprolol|atenolol|losartan|valsartan|hydrochlorothiazide|hctz|omeprazole|pantoprazole|
esomeprazole|amoxicillin|azithromycin|clarithromycin|ciprofloxacin|levofloxacin|doxycycline|
penicillin|cephalexin|sertraline|fluoxetine|escitalopram|citalopram|paroxetine|venlafaxine|
duloxetine|bupropion|trazodone|mirtazapine|gabapentin|pregabalin|tramadol|oxycodone|hydrocodone|
morphine|prednisone|prednisolone|albuterol|montelukast|fluticasone|insulin|glipizide|glyburide|
glimepiride|sitagliptin|empagliflozin|dapagliflozin|liraglutide|semaglutide|ozempic|wegovy|
warfarin|apixaban|rivaroxaban|clopidogrel|aspirin|ibuprofen|naproxen|acetaminophen|paracetamol|
diclofenac|celecoxib|allopurinol|colchicine|furosemide|spironolactone|digoxin|amiodarone|
clonazepam|lorazepam|alprazolam|diazepam|zolpidem|quetiapine|risperidone|olanzapine|aripiprazole|
lamotrigine|valproate|levetiracetam|methotrexate|hydroxychloroquine|adalimumab|tamoxifen|
finasteride|tamsulosin|sumatriptan|ondansetron|methylprednisolone|tacrolimus|isotretinoin
""".replace("\n", "").strip()

# very drug-specific suffixes (anchored, min length) - low false-positive
DRUG_SUFFIX = r"\b[a-z]{3,}(?:mab|tinib|prazole|sartan|dipine|floxacin|parin|coxib|" \
              r"afil|azepam|statin|cillin|gliptin|gliflozin|lukast)\b"

# named lab analytes (need an accompanying number to count)
LABS = r"""
a1c|hba1c|hemoglobin a1c|glucose|fasting glucose|cholesterol|ldl|hdl|triglycerides|
creatinine|egfr|bun|ast|alt|alkaline phosphatase|bilirubin|albumin|tsh|t3|t4|free t4|
hemoglobin|hgb|hematocrit|hct|wbc|rbc|platelets|platelet|sodium|potassium|chloride|
bicarbonate|calcium|magnesium|phosphorus|psa|crp|esr|ferritin|inr|ptt|d-dimer|
troponin|bnp|nt-probnp|vitamin d|b12|folate|cortisol|testosterone|estradiol|hcg|
lipase|amylase|lactate|co2|anion gap|mch|mcv|rdw|hba|microalbumin
""".replace("\n", "").strip()
LAB_UNITS = r"(?:mg/dl|mg/dL|mmol/l|mmol/L|ng/ml|ng/mL|pg/ml|g/dl|g/dL|iu/l|IU/L|u/l|U/L|" \
            r"meq/l|mEq/L|mIU/L|miu/l|µg/dl|mcg/dl|10\^[0-9]|/µl|/ul|mm/hr|mmHg)"

WEAR_DEV = r"(?:fitbit|apple watch|smartwatch|smart watch|oura ring|oura|garmin|whoop|" \
           r"fitness tracker|activity tracker|wearable|continuous glucose monitor|\bcgm\b|" \
           r"pulse oximeter|chest strap|sleep tracker)"
WEAR_METRIC = r"(?:resting heart rate|\brhr\b|heart rate variability|\bhrv\b|vo2 ?max|" \
              r"step count|\d{3,5}\s*steps|hours? of sleep|sleep score|deep sleep|rem sleep|" \
              r"sleep stages?)"

# explicit EHR / pasted-record context
EHR_CTX = r"(?:past medical history|\bpmh\b|\bpmhx\b|problem list|medication list|med list|" \
          r"\bmychart\b|my chart|medical record|health record|\behr\b|\bemr\b|progress note|" \
          r"discharge summary|clinical note|chief complaint|\bicd[- ]?10?\b|" \
          r"vitals?:|meds?:|labs?:|records?:|allergies?:|assessment and plan|\ba&p\b)"

# ---- numeric value detectors (need a clinical anchor nearby) -------------
RE_DRUGS = re.compile(rf"\b(?:{DRUGS})\b", re.I)
RE_DRUG_SUFFIX = re.compile(DRUG_SUFFIX, re.I)
# dose: mg/mcg/units/iu only (drop bare g/ml); exclude lab units like mg/dL
RE_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|units?|iu)\b(?!\s*/\s*d[lL])(?!\w)", re.I)
# patient's-own-medication context (must sit NEAR a drug/dose to count)
RE_MED_CTX = re.compile(r"\b(?:prescribed|prescription (?:for|of)|taking|i take|i'?m on|"
                        r"he'?s on|she'?s on|started (?:on |taking )?|switched to|put on|"
                        r"dose of|current (?:medication|meds)|my (?:medication|meds|prescription|rx)|"
                        r"meds?:|medications?:|meds? (?:list|include)|medications? (?:list|include))\b", re.I)
# "on <drug>" / "<drug> pen" — small window so generic "on" far away doesn't count
RE_ON = re.compile(r"\bon\b", re.I)

RE_LAB_NAME = re.compile(rf"\b(?:{LABS})\b", re.I)
RE_LAB_UNIT = re.compile(LAB_UNITS)
RE_LAB_RESULT_CTX = re.compile(r"\b(?:lab results?|bloodwork|blood work|test results?|"
                               r"my labs|lab values?|labs?:|biopsy (?:showed|result)|"
                               r"pathology (?:report|showed)|urinalysis|trace protein|"
                               r"\bmri (?:showed|results?)|\bct (?:scan )?(?:showed|results?)|"
                               r"\bx-?ray (?:showed|results?)|ultrasound (?:showed|results?))", re.I)

RE_BP = re.compile(r"\b(?:bp|blood pressure)\b[^.\n]{0,15}?\b\d{2,3}\s*/\s*\d{2,3}\b"
                   r"|\b\d{2,3}\s*/\s*\d{2,3}\b\s*(?:mmhg)", re.I)
RE_HR = re.compile(r"\b(?:hr|heart rate|pulse)\b[^.\n]{0,12}?\b\d{2,3}\b"
                   r"|\b\d{2,3}\s*bpm\b", re.I)
RE_TEMP = re.compile(r"\b(?:temp(?:erature)?)\b[^.\n]{0,10}?\b\d{2,3}(?:\.\d)?\b"
                     r"|\b1\d{2}(?:\.\d)?\s*°?\s*f\b|\b3\d(?:\.\d)?\s*°?\s*c\b", re.I)
RE_O2 = re.compile(r"\b(?:spo2|o2 sat|oxygen saturation|o2 saturation)\b[^.\n]{0,10}?\b\d{2,3}\s*%?", re.I)
RE_BMI = re.compile(r"\bbmi\b[^.\n]{0,8}?\b\d{2}(?:\.\d)?\b", re.I)
RE_WT = re.compile(r"\b\d{2,3}\s?(?:lbs?|pounds|kg|kilograms?)\b", re.I)

RE_WEAR_DEV = re.compile(WEAR_DEV, re.I)
RE_WEAR_METRIC = re.compile(WEAR_METRIC, re.I)
RE_EHR = re.compile(EHR_CTX, re.I)

# broad-only: any stated diagnosis / condition history (ubiquitous; tracked separately)
RE_DX = re.compile(r"\b(?:diagnosed with|i have|history of|hx of|suffer from|"
                   r"i was told i have|my (?:condition|diagnosis))\b", re.I)


def _near(txt, rx_a, rx_b, window):
    """True if a match of rx_a sits within `window` chars of a match of rx_b."""
    a = [(m.start(), m.end()) for m in rx_a.finditer(txt)]
    if not a:
        return False
    b = [(m.start(), m.end()) for m in rx_b.finditer(txt)]
    if not b:
        return False
    for s1, e1 in a:
        for s2, e2 in b:
            if max(s1, s2) - min(e1, e2) <= window:
                return True
    return False


def _name_has_number(txt, rx_name, window=12):
    """True if a name match has a digit within `window` chars on either side."""
    for m in rx_name.finditer(txt):
        s, e = m.start(), m.end()
        ctx = txt[max(0, s - 6):min(len(txt), e + window)]
        if any(ch.isdigit() for ch in ctx):
            return True
    return False


RE_DIGIT = re.compile(r"\d")


def user_text(rec):
    """Concatenate only the user turns."""
    lines = []
    for ln in rec["prompt_text"].splitlines():
        if ln.startswith("user:"):
            lines.append(ln[5:])
    return "\n".join(lines) if lines else rec.get("last_user_turn", "")


def detect(txt):
    hits = {}
    # medications: the PATIENT'S OWN med, i.e. a named drug/dose tied to med-context,
    # or a drug name adjacent to a dose. A bare drug name as a topic does NOT count.
    med = (_near(txt, RE_DRUGS, RE_DOSE, 25)              # "metformin 500 mg"
           or _near(txt, RE_DRUGS, RE_MED_CTX, 30)        # "taking metformin"
           or _near(txt, RE_DRUG_SUFFIX, RE_DOSE, 25)
           or _near(txt, RE_DRUG_SUFFIX, RE_MED_CTX, 30)
           or _near(txt, RE_DOSE, RE_MED_CTX, 25)         # "20 mg, my meds:"
           or _near(txt, RE_ON, RE_DRUGS, 4)              # "on warfarin"
           or _near(txt, RE_ON, RE_DRUG_SUFFIX, 4))
    if med:
        hits["medication"] = True
    # labs / test values: named analyte WITH a nearby number, or a lab unit, or result context
    lab = (_name_has_number(txt, RE_LAB_NAME) or RE_LAB_UNIT.search(txt)
           or RE_LAB_RESULT_CTX.search(txt))
    if lab:
        hits["labs"] = True
    # vitals (incl. weight/BMI)
    if (RE_BP.search(txt) or RE_HR.search(txt) or RE_TEMP.search(txt)
            or RE_O2.search(txt) or RE_BMI.search(txt) or RE_WT.search(txt)):
        hits["vitals"] = True
    # wearables
    if RE_WEAR_DEV.search(txt) or RE_WEAR_METRIC.search(txt):
        hits["wearable"] = True
    # explicit EHR / record context
    if RE_EHR.search(txt):
        hits["ehr_record"] = True
    return hits


def main():
    rows = [json.loads(l) for l in SRC.open()]
    cat = Counter()
    strict_n = 0
    broad_n = 0
    dx_only = 0
    out = OUT.open("w")
    for r in rows:
        txt = user_text(r)
        hits = detect(txt)
        strict = bool(hits)
        dx = bool(RE_DX.search(txt))
        broad = strict or dx
        if strict:
            strict_n += 1
            for k in hits:
                cat[k] += 1
        if broad:
            broad_n += 1
        if dx and not strict:
            dx_only += 1
        out.write(json.dumps({
            "example_id": r["example_id"], "themes": r.get("themes", []),
            "strict": strict, "categories": sorted(hits.keys()),
            "dx_mention": dx,
        }) + "\n")
    out.close()
    n = len(rows)

    print(f"HealthBench conversations scanned: {n}\n")
    print("=== Categories of structured user data present in USER turns ===")
    print("(an example can hit multiple categories; % of all 5000)")
    for k in ("medication", "labs", "vitals", "wearable", "ehr_record"):
        c = cat[k]
        print(f"  {k:12s} {c:5d}  {100*c/n:5.1f}%")
    print()
    print("=== Headline ===")
    print(f"  STRICT  (any med/lab/vital/wearable/record value present): "
          f"{strict_n:5d}  {100*strict_n/n:5.1f}%")
    print(f"  BROAD   (strict OR any stated diagnosis/condition history): "
          f"{broad_n:5d}  {100*broad_n/n:5.1f}%")
    print(f"  (diagnosis/history-only, no concrete values: {dx_only} = {100*dx_only/n:.1f}%)")
    print()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
