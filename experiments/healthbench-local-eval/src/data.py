#!/usr/bin/env python3
"""Load a HealthBench split into example records.

The raw JSONL already stores the conversation as a list of {role, content} chat
turns ending in a user turn, so `messages` feeds the chat API directly. Each
rubric item keeps its 0-based index (the stable key used to resume grading).

Splits: "full" (5000), "hard" (1000), "consensus" (3671). `limit` keeps the
first N examples — deterministic, which is all a smoke run needs.
"""
import json
from pathlib import Path

DATA = Path("data")


def axis_of(tags):
    for t in tags:
        if t.startswith("axis:"):
            return t.split(":", 1)[1]
    return None


def load_split(split, limit=None):
    path = DATA / f"healthbench_{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — download it per data/README.md"
        )
    examples = []
    with path.open() as f:
        for line in f:
            ex = json.loads(line)
            rubrics = [
                {
                    "idx": i,
                    "criterion": r.get("criterion", ""),
                    "points": r.get("points", 0),
                    "tags": r.get("tags", []),
                    "axis": axis_of(r.get("tags", [])),
                }
                for i, r in enumerate(ex.get("rubrics", []))
            ]
            examples.append(
                {
                    "example_id": ex["prompt_id"],
                    "messages": ex.get("prompt", []),
                    "rubrics": rubrics,
                    "example_tags": ex.get("example_tags", []),
                }
            )
            if limit is not None and len(examples) >= limit:
                break
    return examples
