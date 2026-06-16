#!/usr/bin/env python3
"""Thin OpenAI-compatible chat client plus two small text helpers.

Deliberately minimal: one POST, raise_for_status, return the content. No retry
or backoff layer — if a call fails the error surfaces so we can see it. Works
unchanged against Ollama and vLLM; only the think-toggle wire format differs.
"""
import json
import re

import requests

import config

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_DANGLING_THINK_RE = re.compile(r"<think>.*\Z", re.DOTALL)  # unclosed tail


def strip_think(text):
    """Remove Qwen3 <think>…</think> reasoning, including an unterminated tail."""
    text = _THINK_RE.sub("", text)
    text = _DANGLING_THINK_RE.sub("", text)
    return text.strip()


def extract_json(text):
    """Return the last balanced {…} JSON object in `text` (after stripping think).

    Raises ValueError if nothing parses — we let that surface rather than guess.
    """
    cleaned = strip_think(text)
    # Drop a ```json … ``` fence if present, then scan for balanced braces.
    cleaned = re.sub(r"```(?:json)?|```", "", cleaned)
    starts = [i for i, c in enumerate(cleaned) if c == "{"]
    for start in reversed(starts):  # prefer the last object the model emitted
        depth = 0
        for j in range(start, len(cleaned)):
            if cleaned[j] == "{":
                depth += 1
            elif cleaned[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : j + 1])
                    except json.JSONDecodeError:
                        break  # malformed; try an earlier '{'
    raise ValueError(f"no parseable JSON object in model output:\n{text}")


def chat(messages, ep, *, temperature, top_p, max_tokens, think):
    """One chat completion. `ep` is a config.Endpoint. Returns the message text
    with any <think> block stripped."""
    messages = [dict(m) for m in messages]  # don't mutate the caller's list

    payload = {
        "model": ep.model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }

    # Toggle Qwen3 thinking per backend.
    if ep.backend == "ollama":
        # Ollama's OpenAI-compat layer accepts a top-level "think" flag.
        payload["think"] = think
    else:
        # vLLM passes through to the chat template via chat_template_kwargs.
        payload["chat_template_kwargs"] = {"enable_thinking": think}
    if not think:
        # Belt-and-suspenders for templates that honour the inline switch.
        messages[-1]["content"] = messages[-1]["content"] + " /no_think"

    resp = requests.post(
        f"{ep.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {ep.api_key}"},
        json=payload,
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    choice = resp.json()["choices"][0]
    if choice.get("finish_reason") == "length":
        # Truncated at max_tokens — with thinking on this usually eats the answer.
        raise RuntimeError(
            f"output truncated at max_tokens={max_tokens} (finish_reason=length); "
            f"raise HB_MAX_TOKENS or disable thinking for this role"
        )
    return strip_think(choice["message"]["content"])
