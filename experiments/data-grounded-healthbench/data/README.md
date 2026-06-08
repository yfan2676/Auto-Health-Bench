# data/

**The HealthBench `.jsonl` files in this directory are git-ignored and must not be committed or reposted.**
The dataset carries a *"do not share examples online to prevent leakage"* notice. Keep raw prompts/rubrics local; our open artifacts publish only the synthetic (Synthea) data, the pipeline, and rubric **diffs/schemas** — never verbatim HealthBench text.

## How to (re)download

```bash
mkdir -p data
curl -sSL -o data/healthbench_full.jsonl      "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl"
curl -sSL -o data/healthbench_hard.jsonl      "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/hard_2025-05-08-21-00-10.jsonl"
curl -sSL -o data/healthbench_consensus.jsonl "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/consensus_2025-05-09-20-00-46.jsonl"
```

Source: [openai/simple-evals](https://github.com/openai/simple-evals) · mirror: [openai/healthbench](https://huggingface.co/datasets/openai/healthbench)

## Files & sizes

| File | Examples | Notes |
|---|---|---|
| `healthbench_full.jsonl` | 5,000 | full benchmark |
| `healthbench_consensus.jsonl` | 3,671 | physician-validated consensus subset |
| `healthbench_hard.jsonl` | 1,000 | hardest examples |

## Record schema (per line)

```
{
  "prompt_id": str,
  "prompt": [ {"role": "user"|"assistant", "content": str}, ... ],   # conversation turns
  "rubrics": [ {"criterion": str, "points": int (-10..10),
                "tags": ["level:example", "axis:<accuracy|completeness|context_awareness|communication_quality|instruction_following>"]} ],
  "example_tags": ["theme:<...>", "physician_agreed_category:<...>"],
  "ideal_completions_data": {...},   # reference completion info
  "canary": str                      # leakage-detection GUID — do not strip
}
```

## Corpus stats (full set)

- 57,237 total rubric criteria (48,562 *unique*); mean 11.4 / example (min 2, max 48).
- **Axis mix:** completeness 38.9%, accuracy 33.0%, context-awareness 15.7%, communication-quality 7.9%, instruction-following 4.5%.
- **Themes (`example_tags`):** global_health 1097, hedging 1071, communication 919, context_seeking 594, emergency_referrals 482, health_data_tasks 477, complex_responses 360.
- **Useful for Phase 1:** `physician_agreed_category` already labels context-dependence — e.g. `context-matters-but-unclear` (219), `enough-context` (227), `context-does-not-matter` (220), `enough-info-to-complete-task` (215). These pre-flag data-enrichable examples.
