# data/

**The HealthBench `.jsonl` files in this directory are git-ignored and must not be committed or reposted.**
The dataset carries a *"do not share examples online to prevent leakage"* notice. Keep raw prompts and rubrics local.

## How to (re)download

```bash
mkdir -p data
curl -sSL -o data/healthbench_full.jsonl      "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl"
curl -sSL -o data/healthbench_hard.jsonl      "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/hard_2025-05-08-21-00-10.jsonl"
curl -sSL -o data/healthbench_consensus.jsonl "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/consensus_2025-05-09-20-00-46.jsonl"
```

The full split (5,000 examples) is enough for everything here; hard (1,000) and consensus (3,671) are optional. Source: [openai/simple-evals](https://github.com/openai/simple-evals).

## Record schema (per line)

```
{
  "prompt_id": str,
  "prompt": [ {"role": "user"|"assistant", "content": str}, ... ],   # conversation, ends on a user turn
  "rubrics": [ {"criterion": str, "points": int (-10..10), "tags": ["axis:<...>", ...]} ],
  "example_tags": ["theme:<...>", "physician_agreed_category:<...>"],
  "canary": str
}
```

## Model setup

Both the target and the judge are Qwen3-4B. Pick one backend.

Mac (Ollama), the default — one server serves both roles:

```bash
ollama pull qwen3:4b
ollama serve            # listens on http://localhost:11434
```

Linux (vLLM, NVIDIA), target and judge on separate GPUs — two servers:

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve Qwen/Qwen3-4B --port 8000   # target
CUDA_VISIBLE_DEVICES=1 vllm serve Qwen/Qwen3-4B --port 8001   # judge
```

then point the harness at vLLM:

```bash
export HB_BACKEND=vllm
export HB_TARGET_BASE_URL=http://localhost:8000/v1  HB_TARGET_MODEL=Qwen/Qwen3-4B
export HB_JUDGE_BASE_URL=http://localhost:8001/v1   HB_JUDGE_MODEL=Qwen/Qwen3-4B
```
