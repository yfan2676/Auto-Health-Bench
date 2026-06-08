#!/usr/bin/env python3
"""Phase 2 (all-30) — build the compact HTML report (-> PDF via Chrome).

For each of the 30 entries, lays out side-by-side:
  ORIGINAL: conversation, original rubric (count + axis mix), data-blind answer
  ENRICHED: injected record, mutated rubric (diff), data-aware answer
  + a score box: data-blind/original, data-aware/original, data-aware/mutated.
A summary page up top aggregates the systematic mis-scoring.

Scores = Σ(points awarded)/Σ(positive points in that rubric), recomputed here
from the graders' per-criterion awards.
"""
import html
import json
from collections import Counter
from pathlib import Path

OUT = Path("results/phase2")
P1 = Path("results/phase1")


def esc(s):
    return html.escape(str(s or ""))


def clip(s, n):
    s = (s or "").strip()
    return esc(s[:n] + " …") if len(s) > n else esc(s)


def possible_pos(rubric, pts="points"):
    return sum(c[pts] for c in rubric if c[pts] > 0) or 1


def grading_sum(gradings, cond, rub):
    for g in gradings:
        if g["condition"] == cond and g["rubric"] == rub:
            return sum(x["points_awarded"] for x in g["per_criterion"])
    return None


def conv_html(conv):
    rows = []
    for line in conv.splitlines():
        if line.startswith(("user:", "assistant:")):
            role, _, txt = line.partition(":")
            rows.append(f'<div class="turn {role}"><b>{role}</b> {esc(txt.strip())}</div>')
        elif line.strip():
            rows.append(f'<div class="turn">{esc(line)}</div>')
    return "\n".join(rows)


def title_of(conv):
    last = [l for l in conv.splitlines() if l.startswith("user:")]
    t = last[-1][5:].strip() if last else conv[:70]
    return esc(t[:80] + ("…" if len(t) > 80 else ""))


CSS = """
@page { size: A4; margin: 12mm 10mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 9.5px;
       color: #1a1a1a; line-height: 1.4; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 13px; margin: 0 0 2px; }
h3 { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color:#555;
     margin: 6px 0 3px; border-bottom: 1px solid #ddd; padding-bottom: 2px; }
.sub { color:#666; font-size: 8.5px; margin-bottom: 2px; }
.entry { page-break-before: always; padding-top: 4px; }
.badges span { display:inline-block; background:#eef2f7; color:#334; border-radius:3px;
     padding:1px 5px; margin:1px 3px 1px 0; font-size:8px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top:4px; }
.col { border:1px solid #e3e3e3; border-radius:5px; padding:6px 8px; }
.col.enriched { background:#fafcff; border-color:#cdd9ec; }
.turn { margin:1px 0; }
.turn b { color:#2451b3; font-weight:600; }
.turn.assistant b { color:#888; font-weight:600; }
.conv { max-height: none; }
.record { white-space: pre-wrap; font-family: ui-monospace, Menlo, monospace; font-size:8px;
     background:#f4f6f8; border-radius:4px; padding:5px 7px; }
.answer { font-size:8.7px; color:#222; background:#fff; border-left:3px solid #ccc; padding:3px 7px; }
.col.enriched .answer { border-left-color:#3a6; }
.diff li { margin:1px 0; font-size:8.3px; }
.rm { color:#a33; } .add { color:#176; }
table.score { border-collapse: collapse; width:100%; margin:3px 0; font-size:9px; }
table.score th, table.score td { border:1px solid #d6d6d6; padding:2px 5px; text-align:center; }
table.score th { background:#f0f0f0; }
.pos { color:#0a7d32; font-weight:700; } .neg { color:#c0271a; font-weight:700; }
.callout { background:#fff7e6; border:1px solid #f0d488; border-radius:4px; padding:4px 8px;
     font-size:8.7px; margin:3px 0; }
.summary table { border-collapse: collapse; width:100%; font-size:8.3px; }
.summary th, .summary td { border:1px solid #ddd; padding:2px 4px; text-align:center; }
.summary td.l { text-align:left; }
.note { color:#555; font-style:italic; font-size:8.2px; margin-top:2px; }
"""


def pct_cell(v):
    if v is None:
        return "<td>—</td>"
    cls = "neg" if v < 0 else "pos"
    return f'<td class="{cls}">{v:.0f}%</td>'


def main():
    cases = json.loads((OUT / "cases_all.json").read_text())
    themes = {r["example_id"]: r.get("_themes", []) for r in
              (json.loads(l) for l in (P1 / "shortlist.jsonl").open())}

    rows, entries = [], []
    for n, case in enumerate(cases, 1):
        eid, id8 = case["example_id"], case["id8"]
        orig = case["original_rubric"]
        rub = json.loads((OUT / f"rubric_{id8}.json").read_text())
        mut = rub["mutated_rubric"]
        grades = json.loads((OUT / f"grade_{id8}.json").read_text())["gradings"]

        po, pm = possible_pos(orig), possible_pos(mut)
        b_o = grading_sum(grades, "baseline", "original")
        r_o = grading_sum(grades, "rawdump", "original")
        r_m = grading_sum(grades, "rawdump", "mutated")
        b_o_p = round(100 * b_o / po) if b_o is not None else None
        r_o_p = round(100 * r_o / po) if r_o is not None else None
        r_m_p = round(100 * r_m / pm) if r_m is not None else None

        rows.append({"n": n, "id8": id8, "title": title_of(case["conversation"]),
                     "b_o": b_o_p, "r_o": r_o_p, "r_m": r_m_p,
                     "d_pen": (r_o_p - b_o_p) if None not in (r_o_p, b_o_p) else None,
                     "d_fix": (r_m_p - r_o_p) if None not in (r_m_p, r_o_p) else None})

        axmix = Counter(c["axis"] for c in orig)
        ax = ", ".join(f"{k} {v}" for k, v in axmix.most_common())
        kept = sum(c["origin"] == "kept" for c in mut)
        rew = sum(c["origin"] == "reweighted" for c in mut)
        added = [c for c in mut if c["origin"] == "added"]
        removed = rub.get("removed_criteria", [])

        diff = []
        for rc in removed[:4]:
            diff.append(f'<li class="rm">− moot: {clip(rc["criterion"],110)} ({rc["points"]:+d})</li>')
        for c in added[:4]:
            diff.append(f'<li class="add">+ added: {clip(c["criterion"],110)} ({c["points"]:+d})</li>')

        badge = "".join(f"<span>{esc(t)}</span>" for t in themes.get(eid, []))
        badge += "".join(f"<span>{esc(t)}</span>" for t in case["profile"].get("primary_change_types", []))

        base_ans = (OUT / f"resp_{id8}_baseline.txt").read_text()
        raw_ans = (OUT / f"resp_{id8}_rawdump.txt").read_text()

        callout = ""
        if None not in (b_o_p, r_o_p, r_m_p):
            callout = (f'Original rubric: data-blind answer <b>{b_o_p}%</b> vs data-aware '
                       f'<b>{r_o_p}%</b> (Δ <b>{r_o_p-b_o_p:+d}pp</b>). '
                       f'Mutated rubric scores the data-aware answer <b>{r_m_p}%</b>.')

        entries.append(f"""
<div class="entry">
  <h2>{n}. {title_of(case['conversation'])}</h2>
  <div class="sub">id {esc(id8)} · {esc(case['n_turns'])} turn(s) · enrichment: {esc(case['profile'].get('enrichment_summary',''))}</div>
  <div class="badges">{badge}</div>

  <table class="score">
    <tr><th>answer ↓ / rubric →</th><th>Original R</th><th>Mutated R′</th></tr>
    <tr><td class="l">data-blind (no record)</td>{pct_cell(b_o_p)}<td>—</td></tr>
    <tr><td class="l">data-aware (record)</td>{pct_cell(r_o_p)}{pct_cell(r_m_p)}</tr>
  </table>
  <div class="callout">{callout}</div>

  <div class="cols">
    <div class="col">
      <h3>Original conversation</h3>
      <div class="conv">{conv_html(case['conversation'])}</div>
      <h3>Original rubric — {len(orig)} criteria</h3>
      <div class="sub">axes: {esc(ax)}</div>
      <h3>Data-blind answer (excerpt)</h3>
      <div class="answer">{clip(base_ans, 650)}</div>
    </div>
    <div class="col enriched">
      <h3>Injected record (Synthea-style)</h3>
      <div class="record">{esc(case['patient_raw_dump'])}</div>
      <h3>Mutated rubric R′ — {kept} kept · {rew} reweighted · {len(added)} added · {len(removed)} removed</h3>
      <ul class="diff">{''.join(diff) or '<li>(see file)</li>'}</ul>
      <h3>Data-aware answer (excerpt)</h3>
      <div class="answer">{clip(raw_ans, 650)}</div>
    </div>
  </div>
</div>""")

    # ---- aggregate summary ----
    def mean(key):
        vs = [r[key] for r in rows if r[key] is not None]
        return sum(vs) / len(vs) if vs else 0
    n_penalized = sum(1 for r in rows if r["d_pen"] is not None and r["d_pen"] < 0)
    sumrows = "\n".join(
        f'<tr><td>{r["n"]}</td><td class="l">{r["title"][:46]}</td>'
        f'{pct_cell(r["b_o"])}{pct_cell(r["r_o"])}{pct_cell(r["r_m"])}'
        f'<td>{r["d_pen"]:+d}</td><td>{r["d_fix"]:+d}</td></tr>'
        for r in rows)

    summary = f"""
<h1>Data-grounded HealthBench — 30-entry showcase</h1>
<div class="sub">Each HealthBench entry is shown as-is and re-evaluated after injecting a
Synthea-style patient record: the conversation, the rubric, and the score, before and after.
Model under test &amp; grader: Claude via subagent (proxy; full HealthBench suite is Phase 4).
Score = Σ(points awarded) / Σ(positive points in that rubric). Negative % = the rubric net-penalizes the answer.</div>

<div class="callout">
<b>Headline:</b> across {len(rows)} entries the original rubric scores the data-blind answer
<b>{mean('b_o'):.0f}%</b> on average but the (correct) data-aware answer only <b>{mean('r_o'):.0f}%</b> —
it <b>penalizes using the record in {n_penalized}/{len(rows)} entries</b>. The mutated rubric restores the
data-aware answer to <b>{mean('r_m'):.0f}%</b>. (Δ-penalize = data-aware−data-blind under Original R;
Δ-fix = Mutated−Original for the data-aware answer.)
</div>

<div class="summary">
<table>
<tr><th>#</th><th class="l">entry</th><th>blind/R</th><th>aware/R</th><th>aware/R′</th><th>Δpen</th><th>Δfix</th></tr>
{sumrows}
</table>
</div>
<div class="note">Caveats: n=30, single model as responder+grader (proxy, pre-physician-validation);
mutated rubrics are LLM-generated hypotheses; records are rendered from the Phase-1 spec (Synthea generator not yet wired).</div>
"""

    page = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{summary}{''.join(entries)}</body></html>"
    (OUT / "report_all.html").write_text(page)

    print(f"wrote {OUT/'report_all.html'} ({len(cases)} entries)")
    print(f"  mean blind/R={mean('b_o'):.0f}%  aware/R={mean('r_o'):.0f}%  aware/R'={mean('r_m'):.0f}%")
    print(f"  original rubric penalizes data use in {n_penalized}/{len(rows)} entries")


if __name__ == "__main__":
    main()
