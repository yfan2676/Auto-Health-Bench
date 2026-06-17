#!/usr/bin/env python3
"""Step 2' — produce the K-value SWEEP of edited conversations (generalizes edit.py).

Instead of a single A->B edit, instantiate the dimension at K~3 values and make one minimal
single-dimension edit per value (delegated to the dimension's editor). Grading the model's
fresh answer to the original V and to each swept V_k (src/sweep_grade.py) then tells us,
behaviorally, which criteria are dimension-DEPENDENT (verdict flips at some value -> footprint)
vs dimension-INDEPENDENT (invariant across the whole sweep -> bridge). This is the "sweep test"
of the idea doc (docs/counterfactual-mutation.md §4.1) — the measured footprint, a stronger
ground truth than a single edit or the a-priori classifier.

For D1 (age) the sweep is an ordered life-stage grid; for D2 (disclosure) it is a few data
renderings of the same fact. Each variant is guarded by a character-diff fraction (and, where
the dimension provides one, a fact-preservation flag) so an edit that changes too much — or
that altered the underlying fact — is flagged ok=False and excluded from analysis.

Output: results/sweep/<example_id>.json
    {example_id, dimension, base_value, values:[v1,...,vK], messages_orig,
     variants: [{value, label, messages_var, replacements:[{find,replace}], n_applied,
                 changed_chars, total_chars, change_frac, ok, extra:{...}}, ...], all_ok}
Resumable: skips items whose sweep file already exists.

Usage:
    python3 src/sweep.py             # sweep every shortlisted item
    python3 src/sweep.py --limit 2
"""
import argparse

import common
import dimensions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N shortlisted items (0 = all)")
    ap.add_argument("--max-change-frac", type=float, default=0.6,
                    help="flag (ok=False) a variant changing more than this fraction of characters")
    args = ap.parse_args()

    shortlist = common.load_shortlist()
    if args.limit:
        shortlist = shortlist[:args.limit]
    by_id = common.examples_by_id([s["example_id"] for s in shortlist])
    common.SWEEP.mkdir(parents=True, exist_ok=True)
    common.endpoints_banner("(sweep)", len(shortlist))

    done = skipped = flagged_items = 0
    for s in shortlist:
        out = common.SWEEP / f"{s['example_id']}.json"
        if out.exists():
            skipped += 1
            continue
        ex = by_id.get(s["example_id"])
        if not ex:
            print(f"skip {s['example_id']}: not found in split")
            continue

        dim_name = s.get("dimension", "age")
        dim = dimensions.get(dim_name)
        base = s.get("base_value", s.get("age_from"))
        values = dim.values(s)
        variants = []
        for v in values:
            res = dim.edit_one(ex["messages"], s, v)
            new_msgs = res["messages_var"]
            changed, total = common.diff_chars(ex["messages"], new_msgs)
            frac = changed / total if total else 0.0
            extra = res.get("extra", {})
            # ok = the reliable diff guard only (applied something, didn't change too much).
            # A dimension's fact-preservation signal (e.g. disclosure) is ADVISORY and kept in
            # `extra` for the viewer — a noisy small-model check shouldn't silently drop data;
            # the bridge-invariance sweep is the real check on whether the edit leaked.
            # A subagent-authored edit is fact-vetted by its (capable) author, so for it the
            # char-diff guard is advisory too: a clinically clean clause-level rewrite (e.g.
            # dropping "without specific readings" when injecting a reading) legitimately exceeds
            # the fraction. change_frac stays recorded/shown; for LLM-rendered edits it still gates.
            vetted = extra.get("source") == "subagent"
            ok = res["n_applied"] > 0 and (vetted or frac <= args.max_change_frac)
            label = f"age {v}" if dim_name == "age" else str(v)
            variants.append({
                "value": v, "label": label, "messages_var": new_msgs,
                "replacements": res.get("replacements", []), "n_applied": res["n_applied"],
                "changed_chars": changed, "total_chars": total, "change_frac": round(frac, 4),
                "ok": ok, "extra": extra,
            })
        all_ok = all(vr["ok"] for vr in variants)
        if not all_ok:
            flagged_items += 1
        common.atomic_write_json(out, {
            "example_id": s["example_id"], "dimension": dim_name,
            "base_value": base, "values": values,
            "messages_orig": ex["messages"], "variants": variants, "all_ok": all_ok,
        })
        done += 1
        flags = "" if all_ok else "  FLAGGED:" + ",".join(
            str(vr["value"]) for vr in variants if not vr["ok"])
        print(f"[{done}] {s['example_id']}  {dim_name} {base} -> {values}  "
              f"{[vr['n_applied'] for vr in variants]} repl, "
              f"max {max(vr['change_frac'] for vr in variants):.1%}{flags}")

    print(f"done: swept {done}, skipped {skipped}, flagged {flagged_items} -> {common.SWEEP}/")


if __name__ == "__main__":
    main()
