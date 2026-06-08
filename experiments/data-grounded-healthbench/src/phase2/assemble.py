#!/usr/bin/env python3
"""Phase 2 / final — Assemble the side-by-side proof-of-concept report.

Recomputes scores from the grader's per-criterion awards (does NOT trust the
grader's reported totals), builds a 3x2 score matrix (baseline/rawdump/summary x
original/mutated rubric) per case, and writes a full side-by-side report.

Outputs (results/phase2/, git-ignored — contains HealthBench text):
    report.md     full side-by-side (prompts, responses, criteria, matrix)
    matrix.json   the numeric score matrices (safe aggregate)
"""
import json
from pathlib import Path

OUT = Path("results/phase2")
CONDS = ["baseline", "rawdump", "summary"]
RUBRICS = ["original", "mutated"]


def possible_positive(rubric):
    return sum(c["points"] for c in rubric if c["points"] > 0)


def main():
    cases = json.loads((OUT / "cases.json").read_text())
    matrices = {}
    md = ["# Phase 2 — proof-of-concept: data-grounded re-evaluation\n",
          "Model under test: **Claude (via subagent)** — a stand-in; the full "
          "HealthBench model suite comes in Phase 4. Responses were generated "
          "rubric-blind (the model only saw the prompt ± patient record).\n",
          "Score = Σ(points awarded) / Σ(positive points in that rubric), "
          "recomputed from per-criterion grades. **Contains HealthBench text — do not share.**\n"]

    for case in cases:
        eid, id8 = case["example_id"], case["id8"]
        orig = case["original_rubric"]
        rub = json.loads((OUT / f"rubric_{id8}.json").read_text())
        mut = rub["mutated_rubric"]
        grades = json.loads((OUT / f"grade_{id8}.json").read_text())["gradings"]
        poss = {"original": possible_positive(orig), "mutated": possible_positive(mut)}

        mat = {c: {} for c in CONDS}
        for g in grades:
            awarded = sum(x["points_awarded"] for x in g["per_criterion"])
            r = g["rubric"]
            mat[g["condition"]][r] = {
                "awarded": round(awarded, 1), "possible": poss[r],
                "pct": round(100 * awarded / poss[r], 0) if poss[r] else None,
            }
        matrices[id8] = {"example_id": eid, "matrix": mat, "possible": poss}

        # ---- report section ----
        md.append(f"\n---\n\n## Case `{id8}` — {', '.join(case['profile']['primary_change_types'])}\n")
        md.append(f"**User asks:** {case['conversation'].splitlines()[-1][:300]}\n")
        md.append(f"**Enrichment:** {case['profile']['enrichment_summary']}\n")
        md.append("**Injected patient record (raw dump):**\n```\n" + case["patient_raw_dump"] + "\n```\n")

        md.append("**Rubric mutation:** "
                  f"{sum(c['origin']=='kept' for c in mut)} kept, "
                  f"{sum(c['origin']=='reweighted' for c in mut)} reweighted, "
                  f"{sum(c['origin']=='added' for c in mut)} added, "
                  f"{len(rub['removed_criteria'])} removed (moot).\n")
        md.append("_Removed as moot (rewarded asking for now-supplied data):_")
        for rc in rub["removed_criteria"]:
            md.append(f"  - ({rc['points']:+d}) {rc['criterion'][:140]}")
        md.append("\n_Added (data-grounded):_")
        for c in [c for c in mut if c["origin"] == "added"]:
            md.append(f"  - ({c['points']:+d}) {c['criterion'][:140]}")

        md.append("\n**Score matrix** (% of possible positive points):\n")
        md.append(f"| response \\ graded by | original R | mutated R' |")
        md.append("|---|---|---|")
        for c in CONDS:
            o = mat[c]["original"]["pct"]
            m = mat[c]["mutated"]["pct"]
            md.append(f"| **{c}** | {o:.0f}% | {m:.0f}% |")

        md.append("\n**Responses (full):**")
        for c in CONDS:
            resp = (OUT / f"resp_{id8}_{c}.txt").read_text().strip()
            md.append(f"\n<details><summary>{c}</summary>\n\n{resp}\n\n</details>")
        md.append("")

    (OUT / "report.md").write_text("\n".join(md))
    (OUT / "matrix.json").write_text(json.dumps(matrices, indent=2))

    # console
    for id8, d in matrices.items():
        print(f"\n=== {id8} (possible: orig={d['possible']['original']}, mut={d['possible']['mutated']}) ===")
        print(f"  {'response':<10} {'origR':>7} {'mutR':>7}")
        for c in CONDS:
            o = d["matrix"][c]["original"]["pct"]
            m = d["matrix"][c]["mutated"]["pct"]
            print(f"  {c:<10} {o:>6.0f}% {m:>6.0f}%")
        b = d["matrix"]["baseline"]; r = d["matrix"]["rawdump"]
        print(f"  Δ orig(rawdump-baseline) = {r['original']['pct']-b['original']['pct']:+.0f}pp "
              f"| Δ mut(rawdump-baseline) = {r['mutated']['pct']-b['mutated']['pct']:+.0f}pp")
    print(f"\nwrote {OUT/'report.md'} + matrix.json")


if __name__ == "__main__":
    main()
