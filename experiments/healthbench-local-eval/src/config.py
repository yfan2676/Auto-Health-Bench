#!/usr/bin/env python3
"""Backend / model configuration, driven entirely by environment variables.

Two endpoints are exposed independently — the target model under test and the
judge model — so that on a Linux/vLLM box they can live on separate GPUs (two
servers, two ports). On a Mac with Ollama both default to the same server, and
since both roles use the same model right now (Qwen3-4B) that is all one process.

Both Ollama and vLLM speak the OpenAI-compatible /v1/chat/completions API, so the
only things that differ between backends are the base URL, the model id, and how
the Qwen3 "thinking" toggle is passed on the wire (handled in llm.py).

Defaults assume the Mac/Ollama path. Override any of these to point at vLLM:

    HB_BACKEND=vllm
    HB_TARGET_BASE_URL=http://localhost:8000/v1   HB_TARGET_MODEL=Qwen/Qwen3-4B
    HB_JUDGE_BASE_URL=http://localhost:8001/v1    HB_JUDGE_MODEL=Qwen/Qwen3-4B
"""
import os
from dataclasses import dataclass

BACKEND = os.environ.get("HB_BACKEND", "ollama").lower()

# Per-backend defaults for the two knobs that actually differ.
_DEFAULTS = {
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen3:4b"},
    "vllm": {"base_url": "http://localhost:8000/v1", "model": "Qwen/Qwen3-4B"},
}


def _backend_default(key):
    return _DEFAULTS.get(BACKEND, _DEFAULTS["ollama"])[key]


# Sampling. Qwen3's recommended settings with thinking enabled are temp 0.6 /
# top_p 0.95. max_tokens must be generous: with thinking on, the reasoning trace
# alone runs ~2.5k tokens before the answer (or the judge's JSON), so a 2048 cap
# truncates mid-thought. 8192 leaves room for reasoning + a long answer; the model
# stops at its natural end (finish_reason "stop") well before the cap.
TEMPERATURE = float(os.environ.get("HB_TEMPERATURE", "0.6"))
TOP_P = float(os.environ.get("HB_TOP_P", "0.95"))
MAX_TOKENS = int(os.environ.get("HB_MAX_TOKENS", "8192"))

# Thinking is on for both roles by default (user choice). <think>…</think> blocks
# are stripped before the answer is saved / the judge JSON is parsed (see llm.py).
THINK_TARGET = os.environ.get("HB_THINK_TARGET", "1") == "1"
THINK_JUDGE = os.environ.get("HB_THINK_JUDGE", "1") == "1"

# Generous client-side timeout — a small local model can still be slow per call.
REQUEST_TIMEOUT = float(os.environ.get("HB_REQUEST_TIMEOUT", "600"))


@dataclass
class Endpoint:
    base_url: str
    model: str
    backend: str
    api_key: str  # neither Ollama nor vLLM needs a real key; "EMPTY" is fine


def target_endpoint():
    return Endpoint(
        base_url=os.environ.get("HB_TARGET_BASE_URL", _backend_default("base_url")),
        model=os.environ.get("HB_TARGET_MODEL", _backend_default("model")),
        backend=BACKEND,
        api_key=os.environ.get("HB_API_KEY", "EMPTY"),
    )


def judge_endpoint():
    # Ollama: judge shares the target server unless overridden. vLLM: a second
    # server on :8001 by default, so target and judge can sit on different GPUs.
    judge_default_url = (
        target_endpoint().base_url
        if BACKEND == "ollama"
        else "http://localhost:8001/v1"
    )
    return Endpoint(
        base_url=os.environ.get("HB_JUDGE_BASE_URL", judge_default_url),
        model=os.environ.get("HB_JUDGE_MODEL", _backend_default("model")),
        backend=BACKEND,
        api_key=os.environ.get("HB_API_KEY", "EMPTY"),
    )
