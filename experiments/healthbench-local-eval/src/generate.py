#!/usr/bin/env python3
"""Phase 1 — generate and save the target model's response to each conversation.

One file per example under results/responses/<example_id>.json. Resumable: an
example whose file already exists is skipped, and each file is written
atomically (temp file + os.replace) so an interrupted run never leaves a partial
file behind. Run this to completion before grading.

Usage (from the experiment directory):
    python3 src/generate.py --split full --limit 25
"""
import argparse
import json
import os
from pathlib import Path

import config
import data
import llm

OUT = Path("results/responses")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=25, help="first N examples (0 = all)")
    args = ap.parse_args()

    ep = config.target_endpoint()
    OUT.mkdir(parents=True, exist_ok=True)
    examples = data.load_split(args.split, args.limit or None)
    print(f"target={ep.model} @ {ep.base_url}  split={args.split}  examples={len(examples)}")

    done = skipped = 0
    for i, ex in enumerate(examples):
        out_path = OUT / f"{ex['example_id']}.json"
        if out_path.exists():
            skipped += 1
            continue
        response = llm.chat(
            ex["messages"], ep,
            temperature=config.TEMPERATURE, top_p=config.TOP_P,
            max_tokens=config.MAX_TOKENS, think=config.THINK_TARGET,
        )
        record = {
            "example_id": ex["example_id"],
            "split": args.split,
            "model": ep.model,
            "think": config.THINK_TARGET,
            "temperature": config.TEMPERATURE,
            "response": response,
        }
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record))
        os.replace(tmp, out_path)
        done += 1
        print(f"[{i+1}/{len(examples)}] {ex['example_id']}  ({len(response)} chars)")

    print(f"done: generated {done}, skipped {skipped} existing -> {OUT}/")


if __name__ == "__main__":
    main()
