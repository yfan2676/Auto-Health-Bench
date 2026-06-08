# Grading spec (Phase 2, compact)

You are a strict, fair model-based grader. For one case `id8` produce THREE gradings:
1. `baseline` response  vs  `original` rubric   (the as-is HealthBench score)
2. `rawdump`  response  vs  `original` rubric   (does the original rubric mis-score the data-aware answer?)
3. `rawdump`  response  vs  `mutated`  rubric   (the data-grounded score)

Per-criterion awarding rule:
- points > 0 (desirable): award FULL points if clearly satisfied, HALF (rounded
  toward zero) if partial, 0 if not.
- points < 0 (undesirable behavior): award the negative points (penalty) if that
  behavior IS present in the response; else 0.
Judge ONLY what the response says. The baseline response had NO record — grade it
honestly (it cannot satisfy record-dependent criteria; that is expected, not a defect).

Output — write ONLY this JSON to `results/phase2/grade_<id8>.json` (must parse):
```json
{
  "example_id": "<full id>",
  "gradings": [
    {"condition":"baseline","rubric":"original",
     "per_criterion":[{"id":<criterion id>,"points_awarded":<number>}],
     "note":"<=140 chars: what it got / missed"},
    {"condition":"rawdump","rubric":"original", "per_criterion":[...], "note":"..."},
    {"condition":"rawdump","rubric":"mutated",  "per_criterion":[...], "note":"..."}
  ]
}
```
Grade EVERY criterion in the relevant rubric (use the rubric's own criterion ids:
integer index for original, the "m#" id for mutated). Keep per_criterion compact
(id + points_awarded only). Totals are recomputed downstream — do not include them.
