# Experiments

Each subfolder here is **one self-contained exploration**. Experiments are independent:
they may use different environments, datasets, and tooling, and each owns its own
results. This is the part of the repo that changes fastest.

Experiments are tagged by the project's research **directions** (see the
[top-level README](../README.md)):

- **A — Automatic rubric generation:** what makes a good rubric; how to auto-generate
  and validate them.
- **B — Data-grounded evaluation:** evaluating health LLMs with the user's real data.
- **A∩B:** data-conditioned rubric generation, where the two directions intersect.

## Index

| Folder | Direction | Status | One line |
|---|---|---|---|
| [`data-grounded-healthbench/`](data-grounded-healthbench/) | B (+ A∩B via rubric mutation) | active — Phase 1 & 2 (PoC) done | Turn HealthBench items into functions of patient data; measure how rubrics and scores shift once the record is present. |

*(Add a row per new experiment. Direction A has no experiment yet — planned.)*

## Anatomy of an experiment

```
<experiment-name>/
├── README.md     # goal, method, how to run, headline findings, data policy
├── src/          # code for THIS experiment
├── data/         # inputs — git-ignored except data/README.md (how to (re)download)
├── results/      # outputs — small reports committed; large/bulk artifacts git-ignored
└── reports/      # method logs & written-up findings (committed)
```

## Conventions

- **Run from the experiment directory.** Scripts resolve paths relative to the current
  working directory (e.g. `Path("data/derived")`), so always
  `cd experiments/<name>` before running `python3 src/...`.
- **Data is never committed.** Put (re)download/generation instructions in
  `data/README.md`. Raw data and large artifacts are git-ignored by the root
  `.gitignore` (`experiments/*/data/*`, plus bulk patterns under `results/`).
- **Commit the small reports.** Markdown method logs, score matrices, and shortlists go
  in `reports/` (or as small files in `results/`) so the findings are versioned.
- **Respect the source-data license.** HealthBench text must not be reposted publicly;
  keep verbatim prompts/rubrics out of committed files unless the repo is private.

## Adding a new experiment

1. `mkdir -p experiments/<name>/{src,data,results,reports}`
2. Add a `README.md` (goal, method, run steps, findings) and a `data/README.md`
   (how to obtain inputs).
3. Add a row to the index table above.
4. If it produces a new kind of bulk artifact, add an ignore pattern to the root
   `.gitignore` under the "BULK / LARGE generated results" block.
