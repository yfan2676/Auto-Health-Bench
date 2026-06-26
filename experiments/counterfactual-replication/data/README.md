# Data

This experiment reads the HealthBench full split, `healthbench_full.jsonl`, which is the same
file the sibling `counterfactual-mutation` experiment uses. It is git-ignored (large, and only a
derived subset is ever published).

`healthbench_full.jsonl` here is a symlink to `../../counterfactual-mutation/data/healthbench_full.jsonl`.
On a fresh clone, recreate it (or set `CM_DATA_DIR` to wherever the split lives):

```bash
ln -sf ../../counterfactual-mutation/data/healthbench_full.jsonl data/healthbench_full.jsonl
```

See `../../counterfactual-mutation/data/README.md` for how to fetch the original split.
