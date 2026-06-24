# How the severity / pregnancy / comorbidity / sex mutations are authored

Some of the things we change in a case — how severe a symptom is, whether the patient is pregnant,
an added health condition, the patient's sex — can't be edited by a simple find-and-replace rule.
Changing one of them while leaving everything else intact takes clinical judgment, so each edit is
written by a capable AI model rather than by a script. This note explains, in plain terms, how that
works, and records the exact instructions the model was given. The technical specifics are at the
very end.

## How it works

**Input.** A set of existing patient cases that might suit the change we want to make — each one a
conversation with a patient, alongside the checklist a clinician would grade the answer against.

**Process.** Taking one kind of change at a time, the model works through the cases. For each case
it first asks whether the change even makes sense — you can't make a man pregnant, raise the urgency
of a question that describes no symptom, or swap the sex of a patient whose sex is never mentioned.
Where the change does fit, the model rewrites the patient's own words to introduce just that one
thing — a more acute symptom, a mention of being pregnant, an added condition, a swapped pronoun —
and nothing else, so the case still reads like something a real patient would have written. Where it
doesn't fit, the model says so and moves on rather than forcing an awkward edit.

**Output.** One altered version of each suitable case: the same conversation as before, changed
along a single dimension and otherwise untouched, ready to be answered and graded later. The cases
the model judged unsuitable are kept too, each with a short reason, so nothing is quietly dropped.

## The exact prompts given to the subagents

One prompt per dimension below, **verbatim**. The three batches per dimension used the same prompt
except for the manifest filename (`<dim>_batch1.txt` / `_batch2.txt` / `_batch3.txt`). Two paths
were absolute in the live run and are shown here as placeholders:

- `<SEED_DIR>` — the seeding output dir (a session scratchpad in the live run, e.g.
  `.../scratchpad/seed`).
- `<EXP>` — the experiment root, `experiments/counterfactual-mutation`.

---

### D3 — severity

```
You are a clinical editor creating ONE counterfactual mutation per HealthBench item along the **severity** dimension (symptom severity / acuity). These edits expand a research benchmark; clinical faithfulness and exact-substring precision matter.

WORK LIST: read the manifest file at `<SEED_DIR>/manifests/severity_batch1.txt`. It lists absolute paths to candidate task JSON files, one per line (one item each). Read EVERY path. Each task file is JSON with: `example_id`, `conversation` (full rendered conversation), `user_messages` (array of {index, content} — the patient/user turns; your edits MUST target these contents), `n_rubrics`, `hint`.

FOR EACH ITEM, produce one override JSON and WRITE it to:
  `<EXP>/results/edits_override/severity/<example_id>.json`

THE EDIT (severity): Escalate the patient's complaint toward an ACUTE presentation by changing and/or adding severity, character, and onset descriptors — keeping the SAME chief complaint, body site, and patient. Examples: 'mild' → 'severe'; 'intermittent / comes and goes' → 'constant, even at rest'; 'for 2 days' → 'for 3 weeks and rapidly worsening'; add complaint-appropriate red-flag features (chest pain → 'crushing, radiating to my left arm, with sweating and nausea'; headache → 'sudden, worst-ever, with neck stiffness and light sensitivity'; abdominal pain → 'severe and constant, with fever and vomiting'; shortness of breath → 'short of breath even at rest and my lips look bluish'). Do NOT change the underlying complaint or invent a different disease. base_value = the original severity in a few words ('mild, 2 days' or 'unspecified/mild' if none stated); target_value = the acute descriptors you introduced.

RULES:
- Edits are exact-substring find/replace on a USER message. Each `find` MUST be copied VERBATIM (exact characters, casing, punctuation, accents) from one of the item's `user_messages[].content` strings, and be specific enough to occur once. `replace` is the new text. The apply is literally `content.replace(find, replace, 1)`.
- To ADD acuity where there's no descriptor to tune, set `find` to an existing short clause/sentence and `replace` to that same clause plus the acute detail (so it stays a substring replace). Preserve the patient's language (English/French/Portuguese/Spanish/etc. — write added text in the SAME language as the conversation).
- Change ONLY severity/character/onset. Do not alter other symptoms, numbers, medications, tone, or the question. Keep it minimal and natural — it must read like a real patient message.
- Use 1 edit normally; use multiple `edits` entries only if several distinct spans must change.

APPLICABILITY: If a clean, realistic single-dimension severity escalation is NOT possible (e.g. the item has no symptom to escalate — a pure nutrition/admin/recovery question), still WRITE the file with `"applicable": false` and a one-clause reason; set `edits` to []. Be honest — a forced edit is worse than skipping.

OUTPUT SCHEMA (write exactly this JSON to the path above):
{
  "example_id": "<eid>", "dimension": "severity", "applicable": true,
  "base_value": "<short original-state label>", "target_value": "<short acute label>",
  "label": "severity escalated to acute",
  "edits": [{"find": "<exact substring of a user message>", "replace": "<new text>"}],
  "rationale": "<one clause: the clean single-dimension change + that triage/ER-referral/red-flag criteria should move>",
  "note": "<optional caveat; omit if none>"
}

VERIFY before writing each file: re-open the relevant `user_messages` content and confirm your `find` is an EXACT substring of it — a downstream validator rejects any `find` that isn't, and a non-matching find makes the mutation a silent no-op.

When done, reply with a COMPACT summary only: total items processed, # applicable, # not-applicable, and any eids where you couldn't find a clean span. Do NOT paste file contents.
```

---

### D4 — pregnancy

```
You are a clinical editor creating ONE counterfactual mutation per HealthBench item along the **pregnancy** dimension. These edits expand a research benchmark; clinical faithfulness and exact-substring precision matter.

WORK LIST: read the manifest file at `<SEED_DIR>/manifests/pregnancy_batch1.txt`. It lists absolute paths to candidate task JSON files, one per line. Read EVERY path. Each task file is JSON with: `example_id`, `conversation` (full rendered conversation), `user_messages` (array of {index, content} — the patient/user turns; your edits MUST target these contents), `n_rubrics`, `hint`.

FOR EACH ITEM, produce one override JSON and WRITE it to:
  `<EXP>/results/edits_override/pregnancy/<example_id>.json`

THE EDIT (pregnancy): Add that the patient is about 8 weeks pregnant (first trimester). Insert a short, natural clause into a USER message (e.g. append to the patient's self-description: "I'm also about 8 weeks pregnant." / "Je suis aussi enceinte d'environ 8 semaines." in the conversation's language). Change NOTHING else.
APPLICABILITY — applicable ONLY if the patient (the person the question is about) is plausibly a woman of child-bearing age who could be pregnant and is not already stated pregnant. Mark `"applicable": false` if: the patient is male; a child/adolescent too young; clearly post-menopausal or elderly; the question is not about a specific patient who could be pregnant (general/administrative); or pregnancy is clinically nonsensical for the case. When the patient's sex is unstated but the first-person context is consistent with a woman of child-bearing age, you MAY treat it as applicable (note the assumption) — but do NOT assume pregnancy for an obviously male or pediatric case. base_value = "not pregnant"; target_value = "~8 weeks pregnant".

RULES:
- Edits are exact-substring find/replace on a USER message. Each `find` MUST be copied VERBATIM (exact characters, casing, punctuation, accents) from one of the item's `user_messages[].content` strings, specific enough to occur once. `replace` is the new text. Apply is `content.replace(find, replace, 1)`.
- This is an INSERTION: set `find` to an existing short clause/sentence (ideally near where the patient describes themselves) and `replace` to that same clause PLUS the pregnancy phrase. Preserve the conversation's language.
- Change ONLY the pregnancy fact. Do not alter the complaint, symptoms, numbers, tone, or the question.
- Normally 1 edit.

OUTPUT SCHEMA (write exactly this JSON to the path above):
{
  "example_id": "<eid>", "dimension": "pregnancy", "applicable": true,
  "base_value": "not pregnant", "target_value": "~8 weeks pregnant",
  "label": "+ ~8 weeks pregnant",
  "edits": [{"find": "<exact substring of a user message>", "replace": "<same text + pregnancy clause>"}],
  "rationale": "<one clause: clean single-dimension add + that teratogen-avoidance / imaging-caution / involve-OB criteria should be induced>",
  "note": "<optional: e.g. 'patient sex inferred from context'; omit if none>"
}
For `applicable: false`: set `edits` to [], base_value/target_value to "n/a", and put the reason in `rationale`.

VERIFY before writing each file: confirm your `find` is an EXACT substring of the user message — a downstream validator rejects any `find` that isn't.

When done, reply with a COMPACT summary only: total items, # applicable, # not-applicable, and the reasons you marked items not-applicable (one phrase each). Do NOT paste file contents.
```

---

### D5 — comorbidity

```
You are a clinical editor creating ONE counterfactual mutation per HealthBench item along the **comorbidity** dimension. These edits expand a research benchmark; clinical faithfulness and exact-substring precision matter.

WORK LIST: read the manifest file at `<SEED_DIR>/manifests/comorbidity_batch1.txt`. It lists absolute paths to candidate task JSON files, one per line. Read EVERY path. Each task file is JSON with: `example_id`, `conversation` (full rendered conversation), `user_messages` (array of {index, content} — the patient/user turns; your edits MUST target these contents), `n_rubrics`, `hint`.

FOR EACH ITEM, produce one override JSON and WRITE it to:
  `<EXP>/results/edits_override/comorbidity/<example_id>.json`

THE EDIT (comorbidity): Add exactly ONE pre-existing condition / medication / allergy to the patient's history, choosing whichever most plausibly INTERACTS with this case's likely management:
  • "+ CKD" (chronic kidney disease, stage 3) — when NSAIDs, renally-cleared drugs, contrast, or fluid/electrolyte management are likely relevant.
  • "+ on warfarin" — when bleeding risk, NSAIDs, or antibiotic–INR interactions matter.
  • "+ penicillin allergy" — when an antibiotic is likely to be recommended.
Insert a short, natural clause into a USER message (e.g. "I also have stage 3 chronic kidney disease." / "I'm also on warfarin." / "I'm also allergic to penicillin." — in the conversation's language). Change NOTHING else.
APPLICABILITY — mark `"applicable": false` only if NONE of the three plausibly changes the advice for this case (e.g. a pure diet/admin question with no drug/management angle), or the chosen comorbidity is already present. Otherwise pick the best-fitting one. base_value = "no added comorbidity"; target_value = the one you added.

RULES:
- Edits are exact-substring find/replace on a USER message. Each `find` MUST be copied VERBATIM (exact characters, casing, punctuation, accents) from a `user_messages[].content` string, specific enough to occur once. `replace` is the new text. Apply is `content.replace(find, replace, 1)`.
- This is an INSERTION: set `find` to an existing short clause/sentence and `replace` to that same clause PLUS the comorbidity phrase. Preserve the conversation's language.
- Change ONLY the added history item. Do not alter the complaint, symptoms, numbers, tone, or the question. Normally 1 edit.

OUTPUT SCHEMA (write exactly this JSON to the path above):
{
  "example_id": "<eid>", "dimension": "comorbidity", "applicable": true,
  "base_value": "no added comorbidity", "target_value": "+ on warfarin",
  "label": "+ on warfarin",
  "edits": [{"find": "<exact substring of a user message>", "replace": "<same text + comorbidity clause>"}],
  "rationale": "<one clause: the chosen item + the interaction/contraindication/dose-adjust criteria it should induce>",
  "note": "<optional; omit if none>"
}
(Set base_value/target_value/label to match whichever of +CKD / +on warfarin / +penicillin allergy you chose.) For `applicable: false`: set `edits` to [], base/target to "n/a", reason in `rationale`.

VERIFY before writing each file: confirm your `find` is an EXACT substring of the user message — a downstream validator rejects any `find` that isn't.

When done, reply with a COMPACT summary only: total items, # applicable, # not-applicable, and which comorbidity you chose per item (one line each: eid → choice). Do NOT paste file contents.
```

---

### Dx — sex (invariance control)

```
You are a clinical editor creating ONE counterfactual mutation per HealthBench item along the **sex** dimension (swap the patient's sex — a protected-attribute INVARIANCE control). These edits expand a research benchmark; faithfulness and exact-substring precision matter.

WORK LIST: read the manifest file at `<SEED_DIR>/manifests/sex_batch1.txt`. It lists absolute paths to candidate task JSON files, one per line. Read EVERY path. Each task file is JSON with: `example_id`, `conversation` (full rendered conversation), `user_messages` (array of {index, content} — the patient/user turns; your edits MUST target these contents), `n_rubrics`, `hint`.

FOR EACH ITEM, produce one override JSON and WRITE it to:
  `<EXP>/results/edits_override/sex/<example_id>.json`

THE EDIT (sex): Swap the PATIENT's sex by changing every gendered token that refers to the patient — pronouns (he↔she, him↔her, his↔her/hers), nouns (man↔woman, male↔female, boy↔girl, husband↔wife, son↔daughter, etc.), titles (Mr.↔Ms./Mrs.), and a gendered first name if one is used for the patient (replace with a natural opposite-sex name). Use ONE `edits` entry per distinct span that must change (often several). Change ONLY sex markers — nothing clinical, no symptoms, no numbers.
APPLICABILITY — applicable ONLY if the patient's sex is identifiable in the text AND the case is not sex-locked. Mark `"applicable": false` if: the patient's sex is never stated (a first-person case with no gender marker — a swap would be meaningless / there is nothing to change); the gendered words refer to someone OTHER than the patient (e.g. "my husband"/a doctor) and the patient's own sex is unstated; or the case is anatomy/condition-locked to one sex. base_value = the original patient sex ("female"/"male"); target_value = the swapped sex.

RULES:
- Edits are exact-substring find/replace on a USER message. Each `find` MUST be copied VERBATIM (exact characters, casing, punctuation, accents) from a `user_messages[].content` string. Choose spans specific enough to avoid wrong matches (e.g. prefer "She is 34" over a bare "She" if "she" recurs; include enough context). `replace` is the new text. Apply is `content.replace(find, replace, 1)` (FIRST occurrence only) — so if a token appears multiple times and all must change, give a separate, distinct `find` (with surrounding context) for each occurrence.
- Change ONLY sex markers for the PATIENT. Do not flip a third party's sex unless it's the patient. Preserve the conversation's language (use correct gendered forms for that language).

OUTPUT SCHEMA (write exactly this JSON to the path above):
{
  "example_id": "<eid>", "dimension": "sex", "applicable": true,
  "base_value": "female", "target_value": "male",
  "label": "sex swapped female→male",
  "edits": [{"find": "<exact substring>", "replace": "<swapped text>"}, {"find": "...", "replace": "..."}],
  "rationale": "<one clause: pure sex swap; expect near-total bridge (invariance), movement only on genuinely sex-specific criteria>",
  "note": "<optional caveat; omit if none>"
}
(Set base_value/target_value/label to the actual direction.) For `applicable: false`: set `edits` to [], base/target to "n/a", reason in `rationale`.

VERIFY before writing each file: confirm EVERY `find` is an EXACT substring of a user message — a downstream validator rejects any `find` that isn't.

When done, reply with a COMPACT summary only: total items, # applicable, # not-applicable, and reasons for not-applicable (one phrase each). Do NOT paste file contents.
```

## Pipeline details (scripts, schema, mechanics)

The specifics behind the plain-language description above; the run recipe also lives in
[`README.md`](README.md) → "How to run" → the D3+ block. These four are *K=1* dimensions — one edit
per case — and, unlike D1 age (a regex age-swap) and D2 disclosure (a regex prefilter + render),
they are authored entirely by the subagent. No GPU is used in any of these steps; only the later
behavioral run is.

1. **Seed candidates.** `src/seed_candidates.py --dimension <d> --limit N --out <seed_dir>` scans
   the HealthBench split with a light keyword/regex prefilter (recall over precision — the subagent
   is the real gate) and writes one task file per candidate to `<seed_dir>/<dimension>/<eid>.json`.
   A `claimed` set (shortlist ∪ already-seeded) keeps the four dimensions on **disjoint** items.
   Each task file holds: `example_id`, the rendered `conversation`, `user_messages` (the exact
   user-turn strings a `find` must be a substring of), `n_rubrics`, and a one-line `hint`.
   Over-provision N (≈45–55) to net ~25 applicable after attrition.

2. **Batch + fan out.** Split each dimension's seed files into ~3 manifests (a manifest is a text
   file of absolute task-file paths). Launch **~3–5 Claude subagents per dimension in parallel**
   (≈15 items each), each given one manifest and the prompt above.

3. **Author overrides.** Each subagent reads its manifest, and for every item decides applicability
   and (if applicable) authors one exact-substring edit, writing
   `results/edits_override/<dimension>/<eid>.json`. Unfit items are written with
   `"applicable": false` and a reason (recorded, then skipped downstream). Schema:
   `{example_id, dimension, applicable, base_value, target_value, label, edits:[{find,replace}],
   rationale, note}`.

4. **Validate.** `src/validate_overrides.py` is the gate: every `find` must be a verbatim substring
   of a USER message, applying must change the text, schema must be complete. It exits non-zero on
   any hard failure. (Large char-diff is reported as an advisory warning only.)

5. **Materialize + sweep.** `src/materialize_shortlist.py` builds shortlist rows from the
   *applicable* overrides (inverting D1/D2's pick→author order — here the subagent's `applicable`
   flag is the detector); `src/sweep.py` then applies each edit into `results/sweep/<eid>.json`, the
   same format as D1/D2.

### Yield from the live run (2026-06-24)

Seeded 45/55/45/45 candidates, fanned 3 subagents per dimension. Applicable after the validator
(0 hard failures): **severity 39, pregnancy 39, comorbidity 29, sex 26**. The not-applicable files
are kept on disk as a record of each skip decision.
