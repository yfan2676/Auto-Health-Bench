# Rubric-mutation spec (Phase 2, general)

Given a HealthBench case — `original_rubric` (list of {id, criterion, points, axis}),
`synthea_patient_spec`, `patient_raw_dump` (the structured record that WILL be
supplied to the model under test), and a `profile` (with `affected_existing_criteria`
and `proposed_added_criteria` as hints) — produce the mutated rubric R' used to
grade a model that was GIVEN this record.

Principles:
1. **Remove as moot** any criterion that rewards *asking for / seeking* information
   that is now present in the supplied record (age, comorbidities, meds, allergies,
   labs, vitals…). A model that re-asks for supplied data should not earn points.
2. **Reweight / rewrite** criteria phrased conditionally ("if you take X…", "if the
   patient has Y…") into definite, data-grounded criteria keyed to what the record
   actually shows.
3. **Add** new data-grounded criteria the record now makes testable — start from
   `profile.proposed_added_criteria` but refine to be specific and checkable. Where
   the record implies a contraindication/safety issue (e.g. a documented allergy vs.
   a suggested drug), add a NEGATIVE criterion that penalizes ignoring/contradicting
   the record.
4. **Keep** clinically valid, data-independent criteria unchanged (origin "kept").
5. Preserve the points scale (−10..+10) and the clinical intent. Stay faithful to
   the supplied record — do not invent values beyond `synthea_patient_spec`.

Output — write ONLY this JSON to `results/phase2/rubric_<id8>.json` (must parse):
```json
{
  "example_id": "<full id>",
  "mutated_rubric": [
    {"id":"m0","criterion":str,"points":int,"axis":str,
     "origin":"kept|reweighted|added","orig_id":int|null,"note":str}
  ],
  "removed_criteria": [ {"orig_id":int,"criterion":str,"points":int,"reason":str} ],
  "rationale": str
}
```
Every original criterion must be accounted for (kept / reweighted / removed).
