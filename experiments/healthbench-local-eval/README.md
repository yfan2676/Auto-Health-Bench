# healthbench-local-eval

Run the standard HealthBench evaluation end to end with local models: a target
model under test answers the conversations, and a local judge model grades each
rubric item. Both roles are Qwen3-4B for now. This is the baseline harness —
faithful to OpenAI's simple-evals methodology — that later experiments can reuse
and compare against. (The sibling `data-grounded-healthbench` experiment used
Claude subagents as an ad-hoc judge; here the judge is real local inference.)

## Method

The grading follows simple-evals exactly. Each rubric item is graded by its own
judge call: the judge sees the full conversation with the model's response
appended as the final assistant turn, plus one rubric item, and returns
`{"explanation", "criteria_met"}`. The grader prompt is vendored verbatim in
`src/grade.py`. An example scores `achieved_points / total_possible_points`,
where the possible points sum the positive-point items and the achieved points
sum every met item (negative items subtract when met). The overall score is the
mean across examples, clipped to [0, 1].

The model under test is served behind an OpenAI-compatible API, so the same code
runs against Ollama (Mac) or vLLM (Linux/NVIDIA). With vLLM the target and judge
can sit on separate GPUs as two servers; see `data/README.md`. Qwen3 thinking is
enabled for both roles by default, and `<think>` blocks are stripped before the
answer is saved and before the judge's JSON is parsed.

## How to run

From this directory, after downloading the data and starting the model server
(`data/README.md`) and installing the one dependency (`pip install requests`):

```bash
python3 src/generate.py --split full --limit 25   # Phase 1: target responses
python3 src/grade.py    --split full --limit 25   # Phase 2: judge each rubric item
python3 src/score.py    --split full --limit 25   # aggregate -> results/score.json
```

`--split` is `full` (default) | `hard` | `consensus`; `--limit` keeps the first N
examples (`0` = all). The default is a 25-example smoke run; raise `--limit` for a
real evaluation. Both phases are resumable — rerun the same command after an
interruption and it continues:

- `generate.py` writes one file per example under `results/responses/` and skips
  any that already exist (atomic writes, so no partial files).
- `grade.py` appends one line per criterion to `results/grades.jsonl` and skips
  `(example, rubric)` pairs already present.

Configuration is environment-driven; see `src/config.py` for every `HB_*` knob
(backend, base URLs, model ids, sampling, thinking toggles).

### Speed note

With thinking on, Qwen3-4B spends roughly 2.5k reasoning tokens (~35–40 s on this
Mac) per judge call before emitting the verdict, so grading dominates runtime: a
25-example run is on the order of a few hours. `HB_MAX_TOKENS` defaults to 8192
because a smaller cap truncates the reasoning before the answer (the client raises
a clear error if a call still hits the cap). To grade far faster — and closer to
the original HealthBench setup, whose GPT-4.1 grader is not a reasoning model —
set `HB_THINK_JUDGE=0` so the judge answers directly; the target can keep thinking
on independently.

## Layout

```
src/config.py     backend + model config (env-driven)
src/llm.py        OpenAI-compatible chat client; think-stripping + JSON extraction
src/data.py       load a HealthBench split
src/generate.py   Phase 1 — target responses (resumable)
src/grade.py      Phase 2 — per-rubric-item judging (resumable); vendors GRADER_TEMPLATE
src/score.py      aggregate into overall + per-axis + per-theme scores
results/          responses/ and grades.jsonl are git-ignored; score.json is committed
```

## Findings

None yet — to be filled in after the first runs.
