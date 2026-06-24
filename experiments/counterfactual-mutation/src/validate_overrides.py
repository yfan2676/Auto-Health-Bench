#!/usr/bin/env python3
"""Validate the subagent-authored D3+ override files before they are swept.

The one critical correctness check is that every `find` is an EXACT SUBSTRING of one of the item's
USER messages — otherwise the deterministic str.replace is a silent no-op and the "mutation" never
happens. We also check the schema, that applying the edits actually changes the conversation, and
report the char-diff fraction (advisory — sweep.py's vetted guard makes it advisory for subagent
edits, but a huge diff is worth eyeballing).

Read-only over results/ and the split. Prints a per-dimension report; exits non-zero if any
applicable override fails a hard check, so it can gate the materialize/sweep steps.

Usage:
    python3 src/validate_overrides.py                 # all D3+ dimensions
    python3 src/validate_overrides.py --dimension severity
"""
import argparse
import json
import sys

import common

DIMS = ("severity", "pregnancy", "comorbidity", "sex")
_REQUIRED = ("example_id", "dimension", "applicable", "base_value", "target_value", "label", "edits")


def _user_contents(ex):
    return [m.get("content", "") for m in ex["messages"] if m.get("role") != "assistant"]


def validate_dim(dimension, by_id):
    d = common.EDITS_OVERRIDE / dimension
    files = sorted(d.glob("*.json")) if d.exists() else []
    applicable = not_applicable = 0
    failures = []  # (eid, reason)
    warnings = []  # (eid, reason)
    for f in files:
        eid = f.stem
        try:
            ov = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            failures.append((eid, f"unreadable JSON: {e}"))
            continue
        if not ov.get("applicable"):
            not_applicable += 1
            continue
        applicable += 1
        missing = [k for k in _REQUIRED if k not in ov]
        if missing:
            failures.append((eid, f"missing keys {missing}"))
            continue
        if ov.get("dimension") != dimension:
            failures.append((eid, f"dimension field {ov.get('dimension')!r} != {dimension!r}"))
        if str(ov.get("base_value", "")).strip() == str(ov.get("target_value", "")).strip():
            failures.append((eid, "base_value == target_value (no contrast)"))
        ex = by_id.get(eid)
        if ex is None:
            failures.append((eid, "example_id not in split"))
            continue
        edits = ov.get("edits") or []
        if not edits:
            failures.append((eid, "empty edits"))
            continue
        user_contents = _user_contents(ex)
        # 1) every `find` is an exact substring of SOME user message
        for j, e in enumerate(edits):
            find = e.get("find", "")
            if "replace" not in e:
                failures.append((eid, f"edit[{j}] missing 'replace'"))
            if not find:
                failures.append((eid, f"edit[{j}] empty 'find'"))
            elif not any(find in c for c in user_contents):
                failures.append((eid, f"edit[{j}] find not a substring of any user message: {find!r}"))
        # 2) applying actually changes the conversation
        new_msgs, applied = [], 0
        for m in ex["messages"]:
            c = m.get("content", "")
            for e in edits:
                fnd, rep = e.get("find", ""), e.get("replace", "")
                if fnd and fnd in c:
                    c = c.replace(fnd, rep, 1)
                    applied += 1
            new_msgs.append({**m, "content": c})
        if applied == 0:
            failures.append((eid, "edits applied 0 replacements"))
        changed, total = common.diff_chars(ex["messages"], new_msgs)
        frac = changed / total if total else 0.0
        cap = 0.30 if dimension in ("pregnancy", "comorbidity") else 0.45
        if frac > cap:
            warnings.append((eid, f"large change_frac {frac:.1%} (>{cap:.0%}); eyeball single-dimension"))
    return {"dimension": dimension, "files": len(files), "applicable": applicable,
            "not_applicable": not_applicable, "failures": failures, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", choices=DIMS, help="default: all D3+ dimensions")
    args = ap.parse_args()
    dims = [args.dimension] if args.dimension else list(DIMS)

    # collect every eid referenced so we load the split once
    want = set()
    for dim in dims:
        d = common.EDITS_OVERRIDE / dim
        if d.exists():
            want.update(f.stem for f in d.glob("*.json"))
    by_id = common.examples_by_id(want) if want else {}

    total_fail = 0
    for dim in dims:
        r = validate_dim(dim, by_id)
        print(f"\n[{dim}] files={r['files']}  applicable={r['applicable']}  "
              f"not_applicable={r['not_applicable']}  "
              f"failures={len(r['failures'])}  warnings={len(r['warnings'])}")
        for eid, reason in r["warnings"]:
            print(f"  WARN  {eid}: {reason}")
        for eid, reason in r["failures"]:
            print(f"  FAIL  {eid}: {reason}")
        total_fail += len(r["failures"])

    print(f"\n{'OK' if total_fail == 0 else 'FAILED'}: {total_fail} hard failure(s) across {dims}")
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
