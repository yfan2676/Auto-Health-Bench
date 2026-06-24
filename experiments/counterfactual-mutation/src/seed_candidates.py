#!/usr/bin/env python3
"""Step 0 (D3+) — seed CANDIDATE items for a subagent-authored dimension.

D3 severity / D4 pregnancy / D5 comorbidity / Dx sex are too semantic to detect by regex (the
way D1 age and D2 disclosure are), so a capable Claude subagent decides applicability AND authors
the edit. This script does the cheap part: a light keyword/regex PREFILTER over the split to raise
the subagent's hit-rate, then dumps one task file per candidate for the subagents to read. It is
read-only over the dataset and writes nothing into results/ — only task files under --out.

The prefilter is deliberately permissive (recall over precision): the subagent makes the final
applicability call and writes "applicable": false for anything unfit. To keep the four new
dimensions on DISJOINT items (cleaner per-dimension analysis), an item already on the shortlist
(D1/D2) or already seeded for another new dimension is skipped.

Task file (one per candidate): <out>/<dimension>/<eid>.json
    {example_id, dimension, n_rubrics, conversation (rendered),
     user_messages: [{index, content}],   # the exact strings a `find` must be a substring of
     hint: "<short per-dimension authoring hint>"}

Usage:
    python3 src/seed_candidates.py --dimension severity   --limit 45 --out /path/to/scratch/seed
    python3 src/seed_candidates.py --dimension pregnancy   --limit 50 --out /path/to/scratch/seed
"""
import argparse
import json
import re
from pathlib import Path

import common
from dimensions.age import detect_age

DIMS = ("severity", "pregnancy", "comorbidity", "sex")

# --- prefilters (permissive; the subagent is the real gate) ------------------
_SEV_SYMPTOMS = re.compile(
    r"\b(chest pain|short(?:ness)? of breath|breathing|headache|migraine|abdominal pain|"
    r"stomach( ache|\s*pain)?|belly pain|back pain|dizz|faint|palpitation|nausea|vomit|"
    r"cough|fever|bleeding|rash|swelling|numbness|weakness|pain|ache|cramp|sore throat)\b", re.I)

_PREG_FEMALE = re.compile(r"\b(she|her|hers|woman|women|female|girl|mother|mom|wife|daughter|"
                          r"sister|aunt|grandmother|lady|gal|F)\b")
_PREG_MALE = re.compile(r"\b(he|him|his|man|men|male|boy|father|dad|husband|son|brother|"
                        r"uncle|grandfather|guy|M)\b")
_PREG_EXCLUDE = re.compile(r"\b(pregnan|breastfeed|breast[- ]?feed|postpartum|lactat|nursing|"
                           r"trimester|gestation|prenatal|in labor)\b", re.I)
_FIRST_PERSON = re.compile(r"\b(I|I'm|I am|I've|my|me|myself)\b")

_COMORB_TREAT = re.compile(
    r"\b(medication|medicine|drug|prescri|dose|dosage|take|taking|treat|therapy|pill|"
    r"ibuprofen|acetaminophen|tylenol|advil|aspirin|nsaid|antibiotic|painkiller|pain reliever|"
    r"manage|should i (take|use)|over[- ]the[- ]counter|otc|supplement)\b", re.I)
_COMORB_EXCLUDE = re.compile(r"\b(ckd|chronic kidney|renal (disease|failure|impairment)|"
                             r"warfarin|coumadin|on a blood thinner|penicillin allerg|allergic to "
                             r"penicillin|amoxicillin allerg)\b", re.I)

_SEX_TOKENS = re.compile(r"\b(he|him|his|she|her|hers|man|woman|men|women|male|female|boy|girl|"
                         r"mr|mrs|ms|gentleman|lady)\b", re.I)
_SEX_LOCKED = re.compile(r"\b(pregnan|breastfeed|postpartum|menstr|periods?|menopaus|ovar|uter|"
                         r"cervi|vagina|prostate|testic|penis|erectile|sperm|menarche|ocps?|"
                         r"oral contraceptive|hysterectomy|pcos|endometri|pap smear|mammogram|"
                         r"gynec|obstetric|hot flash)\b", re.I)


def _user_text(ex):
    return "\n".join(m.get("content", "") for m in ex["messages"] if m.get("role") != "assistant")


def _fits(dimension, ex):
    text = _user_text(ex)
    if not text.strip():
        return False
    if dimension == "severity":
        return bool(_SEV_SYMPTOMS.search(text))
    if dimension == "pregnancy":
        if _PREG_EXCLUDE.search(text):
            return False
        age = detect_age(ex["messages"])
        if age and not (12 <= age[0] <= 50):  # outside plausible child-bearing range
            return False
        female = bool(_PREG_FEMALE.search(text))
        first_person_neutral = bool(_FIRST_PERSON.search(text)) and not _PREG_MALE.search(text)
        return female or first_person_neutral
    if dimension == "comorbidity":
        if _COMORB_EXCLUDE.search(text):
            return False
        return bool(_COMORB_TREAT.search(text))
    if dimension == "sex":
        return bool(_SEX_TOKENS.search(text)) and not _SEX_LOCKED.search(text)
    raise ValueError(dimension)


_HINTS = {
    "severity": "Escalate ONE severity/onset descriptor toward acute (e.g. mild->crushing, "
                "intermittent->at-rest, 2 days->3 weeks, add radiation/diaphoresis). Change nothing "
                "else. Footprint = triage/ER-referral/red-flag.",
    "pregnancy": "Add an '~8 weeks pregnant' (or breastfeeding) clause for an eligible patient; "
                 "change nothing else. Only applicable if the patient could plausibly be pregnant.",
    "comorbidity": "Add ONE history item: '+ CKD' or '+ on warfarin' or '+ penicillin allergy' — "
                   "whichever most plausibly interacts with this case's likely advice. Nothing else.",
    "sex": "Swap the patient's sex (pronouns + gendered nouns) ONLY. Invariance control: applicable "
           "unless the case is sex-locked (anatomy/condition specific to one sex).",
}


def _claimed_eids(out_root):
    """eids already on the shortlist (D1/D2) or already seeded for ANY dimension under out_root,
    so the four new dimensions stay on disjoint items and re-runs don't double-seed."""
    claimed = set()
    if common.SHORTLIST.exists():
        for line in common.SHORTLIST.read_text().splitlines():
            line = line.strip()
            if line:
                claimed.add(json.loads(line)["example_id"])
    if out_root.exists():
        for f in out_root.glob("*/*.json"):
            claimed.add(f.stem)
    return claimed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", required=True, choices=DIMS)
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=45, help="max candidate task files to emit")
    ap.add_argument("--out", required=True, help="task-file output root (e.g. <scratchpad>/seed)")
    args = ap.parse_args()

    out_root = Path(args.out)
    out_dir = out_root / args.dimension
    out_dir.mkdir(parents=True, exist_ok=True)
    claimed = _claimed_eids(out_root)

    examples = common.load_split(args.split, None)
    emitted = scanned = 0
    for ex in examples:
        scanned += 1
        eid = ex["example_id"]
        if eid in claimed:
            continue
        if not _fits(args.dimension, ex):
            continue
        user_msgs = [{"index": i, "content": m.get("content", "")}
                     for i, m in enumerate(ex["messages"]) if m.get("role") != "assistant"]
        convo = "\n\n".join(f"{m['role']}: {m['content']}" for m in ex["messages"])
        common.atomic_write_json(out_dir / f"{eid}.json", {
            "example_id": eid, "dimension": args.dimension,
            "n_rubrics": len(ex["rubrics"]), "conversation": convo,
            "user_messages": user_msgs, "hint": _HINTS[args.dimension],
        })
        claimed.add(eid)
        emitted += 1
        if emitted >= args.limit:
            break

    print(f"scanned {scanned} examples; emitted {emitted} '{args.dimension}' candidate task files "
          f"-> {out_dir}/ (skipped already-claimed eids)")


if __name__ == "__main__":
    main()
