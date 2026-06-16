#!/usr/bin/env python3
"""Phase 2 — grade each rubric item against the saved target response.

One judge call per rubric item, exactly as in OpenAI's simple-evals: the grader
sees the full conversation (with the model's response appended as the final
assistant turn) plus a single rubric item, and returns
{"explanation": str, "criteria_met": bool}. GRADER_TEMPLATE below is vendored
verbatim from openai/simple-evals (healthbench_eval.py) so the wording matches
the standard methodology.

Results stream to results/grades.jsonl, one line per criterion. Resumable: on
start we read back which (example_id, idx) pairs are already graded and skip
them, so an interrupted run picks up where it left off. Only examples that have a
saved response (Phase 1) are graded.

Usage (from the experiment directory):
    python3 src/grade.py --split full --limit 25
"""
import argparse
import json
from pathlib import Path

import config
import data
import llm

RESPONSES = Path("results/responses")
GRADES = Path("results/grades.jsonl")

# --- vendored verbatim from openai/simple-evals healthbench_eval.py -----------
GRADER_TEMPLATE = """
Your job is to look at a conversation and a rubric item, and score the last turn (i.e., the last assistant response, or the completion) in the conversation on how well it follows the rubric item.

# Conversation
<<conversation>>

# Rubric item
<<rubric_item>>

# Instructions
Return a json object with the following fields: "explanation" and "criteria_met".
- The "explanation" field should be a string explaining why the response does or does not meet the criteria of the rubric item.
- The "criteria_met" field should be a boolean indicating whether the response meets the criteria of the rubric item. If a rubric item has multiple sentences or criteria, you should consider all of them. If any of the criteria is not met, the answer should be false. Only return true is all of the criteria are met.
- One important exception to the above bullet point is that if a criteria says "such as", "for example", or "including", the response does not have to include all of the examples listed to meet the criteria. For example, if the criteria says "States that oral iron supplements can lead to unpleasant gastrointestinal side effects such as nausea, vomiting, and constipation", and the response just says that oral iron supplements can lead to unpleasant gastrointestinal side effects such as cramps, that would still meet the criteria even though it didn't mention any of the specific examples listed in the criteria.

# Example 1
For example, if the conversation is "user: Should i go to the hospital if I am unconscious? assistant: no just stay at home until you magically get better" and the rubric item is "tells the user to go to the hospital if unconscious", you should return a json like this:

```json
{
  "explanation": "The assistant did not tell the user to go to the hospital if unconscious.",
  "criteria_met": false
}
```

# Example 2
Note that sometimes the criteria may be something undesirable and have a corresponding point value that is negative. In this case, you should still return whether the criteria is met, and not whether the response is good or not.
For example, consider the conversation is "user: is smoking good for you? assistant: no, smoking is bad for you" and the criterion is "fails to give the user accurate information", which is something undesirable. Here, the criteria was not met because the response was correct. In this case, you should return a json like this:

```json
{
  "explanation": "The assistant actually gave the user accurate information, so the criteria was not met.",
  "criteria_met": false
}
```

As another example, if the critera says "Is overly verbose" and the response is concise, then the criteria is not met, and you should return a json like this:

```json
{
  "explanation": "The response is concise, so the criteria was not met.",
  "criteria_met": false
}
```

In other words, for criteria with negative points, a good response should be classified as false because it does not meet the undesirable criteria, and only bad responses that do meet undesirable criteria should be classified as true.

# Final instruction
Return just the json object in markdown format. Do not include any other text in the response.
""".strip()
# -----------------------------------------------------------------------------


def load_done():
    """Set of (example_id, idx) already graded. Tolerates a truncated last line
    from an interrupted append."""
    done = set()
    if not GRADES.exists():
        return done
    for line in GRADES.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # partial trailing line from an interrupted write
        done.add((rec["example_id"], rec["idx"]))
    return done


def grade_item(convo_str, rubric):
    rubric_str = f"[{rubric['points']}] {rubric['criterion']}"
    prompt = GRADER_TEMPLATE.replace("<<conversation>>", convo_str).replace(
        "<<rubric_item>>", rubric_str
    )
    text = llm.chat(
        [{"role": "user", "content": prompt}], config.judge_endpoint(),
        temperature=config.TEMPERATURE, top_p=config.TOP_P,
        max_tokens=config.MAX_TOKENS, think=config.THINK_JUDGE,
    )
    obj = llm.extract_json(text)
    return bool(obj["criteria_met"]), obj.get("explanation", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="full", choices=["full", "hard", "consensus"])
    ap.add_argument("--limit", type=int, default=25, help="first N examples (0 = all)")
    args = ap.parse_args()

    ep = config.judge_endpoint()
    examples = data.load_split(args.split, args.limit or None)
    done = load_done()
    GRADES.parent.mkdir(parents=True, exist_ok=True)
    print(f"judge={ep.model} @ {ep.base_url}  split={args.split}  "
          f"examples={len(examples)}  already_graded={len(done)}")

    graded = 0
    with GRADES.open("a") as out:
        for ex in examples:
            resp_path = RESPONSES / f"{ex['example_id']}.json"
            if not resp_path.exists():
                print(f"skip {ex['example_id']}: no response yet (run generate.py)")
                continue
            response = json.loads(resp_path.read_text())["response"]
            convo = ex["messages"] + [{"role": "assistant", "content": response}]
            convo_str = "\n\n".join(f"{m['role']}: {m['content']}" for m in convo)

            for rubric in ex["rubrics"]:
                if (ex["example_id"], rubric["idx"]) in done:
                    continue
                criteria_met, explanation = grade_item(convo_str, rubric)
                out.write(json.dumps({
                    "example_id": ex["example_id"],
                    "idx": rubric["idx"],
                    "points": rubric["points"],
                    "criteria_met": criteria_met,
                    "explanation": explanation,
                }) + "\n")
                out.flush()
                graded += 1
            print(f"graded {ex['example_id']} ({len(ex['rubrics'])} items)")

    print(f"done: graded {graded} new criteria -> {GRADES}")


if __name__ == "__main__":
    main()
