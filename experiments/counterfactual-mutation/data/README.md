# data/

This experiment reuses the **same HealthBench split** as
[`../../healthbench-local-eval`](../../healthbench-local-eval/) — no separate copy is
needed. `src/common.py` resolves the data directory automatically, in order:

1. `$CM_DATA_DIR` (if set and it contains `healthbench_full.jsonl`),
2. this directory (`experiments/counterfactual-mutation/data/`),
3. the sibling `experiments/healthbench-local-eval/data/`.

So if you already downloaded the data for the baseline harness, **you don't need to do
anything**. Otherwise, fetch it here (same source + the same do-not-share notice applies —
keep raw prompts/rubrics local, never commit them):

```bash
mkdir -p data
curl -sSL -o data/healthbench_full.jsonl "https://openaipublic.blob.core.windows.net/simple-evals/healthbench/2025-05-07-06-14-12_oss_eval.jsonl"
```

The `.jsonl` files in this directory are git-ignored.
