#!/usr/bin/env python3
"""Shared helpers for the counterfactual-mutation experiment.

We reuse the `healthbench-local-eval` baseline harness (sibling experiment) for the
OpenAI-compatible chat client (`llm`) and the vendored HealthBench grader
(`GRADER_TEMPLATE`), so the grading methodology is *identical* to the standard eval and
not re-implemented here. Endpoints + target/judge model come from the same `HB_*` env
vars (see `healthbench-local-eval/src/config.py`). This experiment adds `CM_*` knobs for
the locality test — most importantly a temperature-0 judge so that any verdict change is
attributable to the conversation edit, not to judge sampling noise.

Run every script from this experiment's directory (paths are relative to it):
    cd experiments/counterfactual-mutation
    export HB_BACKEND=vllm HB_TARGET_BASE_URL=http://localhost:8000/v1 \
           HB_TARGET_MODEL=Qwen/Qwen3-4B \
           HB_JUDGE_BASE_URL=http://localhost:8000/v1 HB_JUDGE_MODEL=Qwen/Qwen3-4B
    python3 src/pick.py --limit 30
    ...
"""
import difflib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# --- bridge to the sibling healthbench-local-eval harness --------------------
_HERE = Path(__file__).resolve().parent
_EXP = _HERE.parent
_HB_DIR = (_EXP / ".." / "healthbench-local-eval").resolve()
_HB_SRC = _HB_DIR / "src"
if not _HB_SRC.exists():
    raise SystemExit(f"sibling harness not found at {_HB_SRC} — expected healthbench-local-eval next to this experiment")
sys.path.insert(0, str(_HB_SRC))

import config            # noqa: E402  sibling config (HB_* env-driven endpoints/sampling)
import llm               # noqa: E402  OpenAI-compatible chat client + think/json helpers
from grade import GRADER_TEMPLATE  # noqa: E402  vendored verbatim from openai/simple-evals

# --- this experiment's knobs (CM_*) ------------------------------------------
# Judge at temperature 0 for the locality test: the only thing that varies between the
# original and edited grading is the conversation, so a deterministic judge isolates the
# edit's effect. Author steps (edit / footprint) keep thinking on for better reasoning.
CM_JUDGE_TEMP = float(os.environ.get("CM_JUDGE_TEMP", "0"))
CM_JUDGE_THINK = os.environ.get("CM_JUDGE_THINK", "0") == "1"
CM_AUTHOR_THINK = os.environ.get("CM_AUTHOR_THINK", "1") == "1"
CM_AUTHOR_TEMP = float(os.environ.get("CM_AUTHOR_TEMP", "0.6"))

# Per-endpoint grading concurrency. The grader calls are independent and stateless
# (one POST each, see llm.chat), so we fan them across the judge endpoints with a
# thread pool to saturate every GPU instead of the ~1 req/s serial baseline. The
# total worker count is len(JUDGE_EPS) * CM_JUDGE_CONCURRENCY. Concurrency does not
# change any call's inputs, so a temperature-0 judge stays deterministic per call.
CM_JUDGE_CONCURRENCY = int(os.environ.get("CM_JUDGE_CONCURRENCY", "8"))

# All judge endpoints (one per GPU when HB_JUDGE_BASE_URLS lists several). Computed
# once; pmap round-robins work across them.
JUDGE_EPS = config.judge_endpoints()

# --- paths -------------------------------------------------------------------
RESULTS = _EXP / "results"
SHORTLIST = RESULTS / "shortlist.jsonl"
VARIANTS = RESULTS / "variants"     # per-item edited conversation V' (single-edit path)
FOOTPRINT = RESULTS / "footprint"   # per-item a-priori per-criterion prediction
ANSWERS = RESULTS / "answers"       # per-item fixed model answer to V (and optionally V')
GRADES = RESULTS / "grades"         # per-item paired grades (orig vs variant, single-edit path)
SWEEP = RESULTS / "sweep"           # per-item K-value sweep of edited conversations
SWEEP_GRADES = RESULTS / "sweep_grades"  # per-item K-way grades (orig + each swept value)


# --- data loading (resolve the HealthBench split flexibly) -------------------
def data_dir():
    """Use CM_DATA_DIR, else this experiment's data/, else the sibling's data/."""
    cands = [os.environ.get("CM_DATA_DIR"), _EXP / "data", _HB_DIR / "data"]
    for c in cands:
        if c and (Path(c) / "healthbench_full.jsonl").exists():
            return Path(c)
    return _EXP / "data"


def _axis_of(tags):
    for t in tags:
        if t.startswith("axis:"):
            return t.split(":", 1)[1]
    return None


def load_split(split="full", limit=None):
    """Same record shape as the sibling data.py, but with flexible data-dir resolution."""
    path = data_dir() / f"healthbench_{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — see data/README.md")
    examples = []
    with path.open() as f:
        for line in f:
            ex = json.loads(line)
            rubrics = [
                {"idx": i, "criterion": r.get("criterion", ""), "points": r.get("points", 0),
                 "tags": r.get("tags", []), "axis": _axis_of(r.get("tags", []))}
                for i, r in enumerate(ex.get("rubrics", []))
            ]
            examples.append({
                "example_id": ex["prompt_id"],
                "messages": ex.get("prompt", []),
                "rubrics": rubrics,
                "example_tags": ex.get("example_tags", []),
            })
            if limit and len(examples) >= limit:
                break
    return examples


def load_shortlist():
    if not SHORTLIST.exists():
        raise FileNotFoundError(f"{SHORTLIST} not found — run src/pick.py first")
    out = []
    for line in SHORTLIST.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def examples_by_id(ids, split="full"):
    """Return {example_id: example} for the requested ids (loads the whole split once)."""
    want = set(ids)
    return {e["example_id"]: e for e in load_split(split, None) if e["example_id"] in want}


# --- LLM helpers (all routed through the sibling client) ---------------------
def convo_string(messages, answer):
    """Render conversation + a fixed assistant answer the way the grader expects."""
    convo = list(messages) + [{"role": "assistant", "content": answer}]
    return "\n\n".join(f"{m['role']}: {m['content']}" for m in convo)


def judge_criterion(convo_str, rubric, *, endpoint=None, temperature=None, think=None):
    """One HealthBench grader call for a single criterion. Returns (criteria_met, explanation).

    `endpoint` lets a pmap worker pin a specific judge server (GPU); defaults to the
    single configured judge endpoint for serial callers.
    """
    endpoint = endpoint or config.judge_endpoint()
    temperature = CM_JUDGE_TEMP if temperature is None else temperature
    think = CM_JUDGE_THINK if think is None else think
    rubric_str = f"[{rubric['points']}] {rubric['criterion']}"
    prompt = GRADER_TEMPLATE.replace("<<conversation>>", convo_str).replace("<<rubric_item>>", rubric_str)
    text = llm.chat([{"role": "user", "content": prompt}], endpoint,
                    temperature=temperature, top_p=config.TOP_P,
                    max_tokens=config.MAX_TOKENS, think=think)
    obj = llm.extract_json(text)
    return bool(obj["criteria_met"]), obj.get("explanation", "")


def pmap(fn, items, *, workers=None):
    """Run `fn(item, endpoint)` over `items` concurrently, round-robining the judge
    endpoints so the work spreads across every GPU. Results are returned in input
    order. A call that raises is caught and its slot becomes an Exception instance —
    the caller decides what to do (skip + log) so one bad grade can't abort a run of
    thousands. With one endpoint this is still a useful within-GPU concurrency layer.
    """
    items = list(items)
    if not items:
        return []
    n_eps = len(JUDGE_EPS)
    workers = workers or max(1, n_eps * CM_JUDGE_CONCURRENCY)

    def _call(i_item):
        i, item = i_item
        ep = JUDGE_EPS[i % n_eps]
        try:
            return fn(item, ep)
        except Exception as e:  # noqa: BLE001 — return it so the run continues
            return e

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_call, enumerate(items)))


def diff_chars(orig_msgs, new_msgs):
    """Characters changed between two conversations (insert/replace/delete). Used by
    the edit guards to flag edits that touch too much text."""
    o = "\n".join(m.get("content", "") for m in orig_msgs)
    n = "\n".join(m.get("content", "") for m in new_msgs)
    sm = difflib.SequenceMatcher(a=o, b=n)
    changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return changed, max(len(o), len(n))


def author_chat(prompt, *, think=None, temperature=None, max_tokens=None):
    """An authoring call (criterion-footprint classification, age edit) on the judge model."""
    think = CM_AUTHOR_THINK if think is None else think
    temperature = CM_AUTHOR_TEMP if temperature is None else temperature
    return llm.chat([{"role": "user", "content": prompt}], config.judge_endpoint(),
                    temperature=temperature, top_p=config.TOP_P,
                    max_tokens=max_tokens or config.MAX_TOKENS, think=think)


def author_json(prompt, **kw):
    return llm.extract_json(author_chat(prompt, **kw))


def target_answer(messages):
    """Generate the model-under-test's answer to a conversation (target endpoint, thinking on)."""
    ep = config.target_endpoint()
    return llm.chat(messages, ep, temperature=config.TEMPERATURE, top_p=config.TOP_P,
                    max_tokens=config.MAX_TOKENS, think=config.THINK_TARGET)


def atomic_write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj))
    os.replace(tmp, path)


def endpoints_banner(split, n):
    t = config.target_endpoint()
    judge_urls = ",".join(ep.base_url for ep in JUDGE_EPS)
    print(f"target={t.model}@{t.base_url}  judge={JUDGE_EPS[0].model}@[{judge_urls}]  "
          f"judge_temp={CM_JUDGE_TEMP} judge_think={CM_JUDGE_THINK} "
          f"concurrency={len(JUDGE_EPS)}x{CM_JUDGE_CONCURRENCY}  split={split}  items={n}")
