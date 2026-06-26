#!/usr/bin/env python3
"""Step 4 — does the mutation move the overall rubric score? Per-dimension significance.

Reads the per-criterion grades (results/grades_<version>/<eid>.jsonl: orig x CR_RUNS + mut x
CR_RUNS verdicts) and, for each sample, computes the HealthBench per-answer score
(common.rubric_score = achieved / total possible points) for every run of each condition.

Per sample (over criteria graded in ALL 2*CR_RUNS cells, so orig and mut share one denominator):
    orig_score[r], mut_score[r]  for r in 0..CR_RUNS-1
    orig_mean = mean_r orig_score[r],  mut_mean = mean_r mut_score[r]
    delta_i   = mut_mean - orig_mean         (the per-sample mutation effect)

Per dimension (over its ~25 samples):
    overall score per run r = mean over samples of that sample's score[r]
    change in overall score  = mut_overall - orig_overall  (absolute + per-run up/down direction)
    SD of the 3 ORIGINAL runs = stdev of the 3 original overall scores (the run-to-run noise floor)
    significance: PAIRED across the 25 samples on {delta_i} — paired t-test (primary), plus a
        sign-flip permutation test and a Wilcoxon signed-rank test (robustness). See src/stats.py.

Output: results/metrics.json + results/report.md

Usage:
    python3 src/analyze.py
"""
import argparse
import json
import os
import statistics

import common
import stats

RUNS = common.CR_RUNS
SEED = int(os.environ.get("CR_SEED", "20260626"))
PERM_R = int(os.environ.get("CR_PERM", "100000"))


def _read_jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _sample_scores(rows):
    """From one sample's grade rows return (orig_scores, mut_scores, n_criteria) or None.

    Only criteria with all CR_RUNS verdicts on BOTH conditions are scored, so every run is over
    an identical criterion set. Returns lists of length CR_RUNS, or None if the sample is not
    scorable (no usable criteria / no positive points)."""
    def cells_ok(rec, cond):
        cs = rec.get(cond, [])
        return len(cs) >= RUNS and all(c.get("verdict") is not None for c in cs[:RUNS])

    usable = [r for r in rows if cells_ok(r, "orig") and cells_ok(r, "mut")]
    if not usable:
        return None
    orig_scores, mut_scores = [], []
    for r in range(RUNS):
        o = common.rubric_score([{"points": rec["points"], "criteria_met": rec["orig"][r]["verdict"]}
                                 for rec in usable])
        m = common.rubric_score([{"points": rec["points"], "criteria_met": rec["mut"][r]["verdict"]}
                                 for rec in usable])
        if o is None or m is None:
            return None
        orig_scores.append(o)
        mut_scores.append(m)
    return orig_scores, mut_scores, len(usable)


def _sd(xs):
    return statistics.stdev(xs) if len(xs) >= 2 else None


def _sign(x, eps=1e-9):
    return "+" if x > eps else ("-" if x < -eps else "0")


def analyze_dimension(samples):
    """samples: list of dicts with orig_scores/mut_scores (length RUNS). Returns a metrics block."""
    n = len(samples)
    deltas = [s["mut_mean"] - s["orig_mean"] for s in samples]
    # Dimension overall score per run = mean over samples of that run's score.
    orig_run = [statistics.fmean(s["orig_scores"][r] for s in samples) for r in range(RUNS)]
    mut_run = [statistics.fmean(s["mut_scores"][r] for s in samples) for r in range(RUNS)]
    orig_overall = statistics.fmean(orig_run)
    mut_overall = statistics.fmean(mut_run)
    delta = mut_overall - orig_overall
    per_run_delta = [mut_run[r] - orig_run[r] for r in range(RUNS)]
    runs_up = sum(1 for x in per_run_delta if x > 1e-9)
    runs_down = sum(1 for x in per_run_delta if x < -1e-9)
    tests = stats.summarize(deltas, perm_R=PERM_R, seed=SEED)
    ttp = tests["ttest"]["p"]
    return {
        "n": n,
        "orig_overall": orig_overall,
        "mut_overall": mut_overall,
        "delta": delta,
        "abs_delta": abs(delta),
        "delta_sign": _sign(delta),
        "orig_run_scores": orig_run,
        "mut_run_scores": mut_run,
        "orig_run_sd": _sd(orig_run),     # SD of the 3 ORIGINAL-run overall scores (headline noise floor)
        "mut_run_sd": _sd(mut_run),
        "per_run_delta": per_run_delta,
        "runs_up": runs_up,
        "runs_down": runs_down,
        "runs_flat": RUNS - runs_up - runs_down,
        "mean_per_sample_orig_run_sd": (statistics.fmean([s["orig_run_sd"] for s in samples
                                                          if s["orig_run_sd"] is not None])
                                        if any(s["orig_run_sd"] is not None for s in samples) else None),
        "ttest": tests["ttest"],
        "perm": tests["perm"],
        "wilcoxon": tests["wilcoxon"],
        "cohens_dz": tests["ttest"].get("dz"),
        "significant": (ttp is not None and ttp < 0.05),
    }


def main():
    argparse.ArgumentParser().parse_args()

    selection = common.load_selection()
    dim_of = {s["example_id"]: s.get("dimension", "age") for s in selection}
    label_of = {s["example_id"]: s.get("chosen_label", "") for s in selection}

    # Build per-sample score records from the grade files.
    samples = []
    for s in selection:
        eid = s["example_id"]
        rows = _read_jsonl(common.GRADES / f"{eid}.jsonl")
        if not rows:
            continue
        sc = _sample_scores(rows)
        if sc is None:
            continue
        orig_scores, mut_scores, n_crit = sc
        samples.append({
            "example_id": eid, "dimension": dim_of.get(eid, "age"), "label": label_of.get(eid, ""),
            "orig_scores": orig_scores, "mut_scores": mut_scores,
            "orig_mean": statistics.fmean(orig_scores), "mut_mean": statistics.fmean(mut_scores),
            "orig_run_sd": _sd(orig_scores), "mut_run_sd": _sd(mut_scores),
            "delta": statistics.fmean(mut_scores) - statistics.fmean(orig_scores),
            "n_criteria": n_crit,
        })

    if not samples:
        raise SystemExit(f"no scorable samples found in {common.GRADES} — run grade.py first")

    by_dim = {}
    dims = sorted({s["dimension"] for s in samples})
    for d in dims:
        members = [s for s in samples if s["dimension"] == d]
        if len(members) >= 1:
            by_dim[d] = analyze_dimension(members)
    by_dim["all"] = analyze_dimension(samples)  # pooled across dimensions

    n_per_dim = {d: sum(1 for s in samples if s["dimension"] == d) for d in dims}
    metrics = {
        "version": common._VERSION, "runs": RUNS, "seed": SEED, "perm_R": PERM_R,
        "judge_temp": common.CM_JUDGE_TEMP, "judge_think": common.CM_JUDGE_THINK,
        "n_samples": len(samples), "n_samples_per_dim": n_per_dim,
        "by_dimension": by_dim,
        "samples": [{k: s[k] for k in ("example_id", "dimension", "label", "orig_scores",
                                       "mut_scores", "orig_mean", "mut_mean", "orig_run_sd",
                                       "delta", "n_criteria")} for s in samples],
    }
    common.atomic_write_json(common.RESULTS / "metrics.json", metrics)
    _write_report(metrics)

    print(f"version={common._VERSION} runs={RUNS} samples={len(samples)} ({', '.join(f'{d}={n_per_dim[d]}' for d in dims)})")
    for d in dims + ["all"]:
        m = by_dim[d]
        sig = "SIGNIFICANT" if m["significant"] else "n.s."
        print(f"  {d:12s} Δ={m['delta']*100:+.2f}%  origSD={_fmtpct(m['orig_run_sd'])}  "
              f"t-p={_fmtp(m['ttest']['p'])} perm-p={_fmtp(m['perm']['p'])} wilcox-p={_fmtp(m['wilcoxon']['p'])}  [{sig}]")
    print(f"-> {common.RESULTS/'metrics.json'}  and  {common.RESULTS/'report.md'}")


def _fmtpct(x):
    return "n/a" if x is None else f"{x*100:.2f}%"


def _fmtp(p):
    if p is None:
        return "n/a"
    return f"{p:.4f}" if p >= 1e-4 else f"{p:.1e}"


def _signed_pct(x):
    return "n/a" if x is None else f"{x*100:+.2f}%"


def _write_report(metrics):
    runs = metrics["runs"]
    dims = sorted(d for d in metrics["by_dimension"] if d != "all")
    L = [
        "# Counterfactual mutation — effect on the overall score (significance)", "",
        f"- model (answer + judge): **{metrics['version']}**, thinking on, judge temp "
        f"**{metrics['judge_temp']}** (think={metrics['judge_think']})",
        f"- replication: **{runs}** independent (answer + grade) runs for the original input and "
        f"**{runs}** for the chosen mutation, per sample",
        f"- samples: **{metrics['n_samples']}** total "
        f"({', '.join(f'{d}={metrics['n_samples_per_dim'][d]}' for d in dims)})",
        f"- significance unit: paired across samples (per-sample score = mean over its {runs} runs); "
        f"primary test = paired t-test, with sign-flip permutation (R={metrics['perm_R']}) and "
        "Wilcoxon signed-rank as robustness checks", "",
        "## Change in overall score per dimension", "",
        "> Overall score = mean per-sample HealthBench rubric score (achieved / possible points). "
        f"\"Runs ↑/↓\" pairs each of the {runs} mutated runs with the same-numbered original run and "
        "counts how many went up vs down. \"Orig run SD\" is the std-dev of the "
        f"{runs} original-run overall scores: the run-to-run noise floor with NO input change.", "",
        f"| dimension | n | orig overall | mut overall | Δ overall | runs ↑/↓ | orig run SD |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in dims + ["all"]:
        m = metrics["by_dimension"][d]
        L.append(f"| {d} | {m['n']} | {_fmtpct(m['orig_overall'])} | {_fmtpct(m['mut_overall'])} | "
                 f"**{_signed_pct(m['delta'])}** | {m['runs_up']}↑ / {m['runs_down']}↓ | "
                 f"{_fmtpct(m['orig_run_sd'])} |")
    L += [
        "", "## Significance — did the mutation really move the score?", "",
        "> H0: the mutation does not change the per-sample score. Paired t-test on the "
        f"{runs}-run-averaged per-sample deltas (mut − orig). Cohen's d_z = mean(delta) / sd(delta). "
        "Significant = paired t-test p < 0.05.", "",
        "| dimension | n | mean Δ | Cohen d_z | t (df) | **t-test p** | perm p | wilcoxon p | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in dims + ["all"]:
        m = metrics["by_dimension"][d]
        tt = m["ttest"]
        tval = "n/a" if tt["t"] is None else f"{tt['t']:.2f} ({tt['df']})"
        dz = "n/a" if m["cohens_dz"] is None else f"{m['cohens_dz']:+.2f}"
        verdict = "**significant**" if m["significant"] else "n.s."
        L.append(f"| {d} | {m['n']} | {_signed_pct(m['delta'])} | {dz} | {tval} | "
                 f"**{_fmtp(tt['p'])}** | {_fmtp(m['perm']['p'])} | {_fmtp(m['wilcoxon']['p'])} | {verdict} |")
    L += [
        "", "## How to read this", "",
        "- **Δ overall** is the absolute movement of the dimension's overall score when the input is "
        "mutated. Its sign and the **runs ↑/↓** column say whether the mutation tended to raise or "
        "lower the score, and how consistent that was across the replicate runs.",
        "- **Orig run SD** is the model's own run-to-run noise (same input, resampled). A Δ overall "
        "that is small relative to this SD is within noise; the paired test is what decides whether "
        "the per-sample shift is real once that noise is accounted for.",
        "- **t-test p** is the primary verdict; **perm** and **wilcoxon** are distribution-light "
        "robustness checks. They should broadly agree. With ~25 samples the Wilcoxon normal "
        "approximation is indicative.",
        "- **all** pools every sample across dimensions (paired the same way); it is the overall "
        "answer to \"does mutating an input dimension move the score at all\".",
        "",
        "_Generated by src/analyze.py. Each sample contributes one original and one mutated input; "
        f"both are answered and graded {runs}x against the SAME original rubric, so a score change "
        "reflects only the changed input._",
    ]
    (common.RESULTS / "report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
