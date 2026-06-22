# Environment & runbook — serving Qwen3.6-27B-FP8 and continuing the run

This experiment has **two roles** with very different dependencies:

| role | what runs it | dependency |
|---|---|---|
| **client** (the pipeline) | `src/*.py`, the `*.sh` drivers, `analyze.py`, `build_viewer.py` | `pip install requests` only — pure HTTP, runs anywhere, no GPU, no `vllm` import |
| **server** (model under test + judge) | `vllm serve Qwen/Qwen3.6-27B-FP8` | a GPU + the heavy `vllm-qwen36` env below |

Only the **server** needs the heavy env. The pipeline talks to it over `HB_*_BASE_URLS`. So to move to
another cluster you rebuild the server env there, point the drivers at it, and (to *continue* rather
than restart) copy the git-ignored intermediate state across — see [Continuing on a new cluster](#continuing-the-run-on-a-new-cluster).

---

## 1. Build the server env (`vllm-qwen36`)

Qwen3.6-27B is arch `qwen3_5` (`Qwen3_5ForConditionalGeneration`), a hybrid (Gated-DeltaNet linear +
full attention) FP8 multimodal model released 2026-04. It needs **vLLM ≥ 0.20 + transformers 5.x**, so
it gets its own conda env, isolated from the proven 4B `vllm` env. Exact versions known-good on the
build box (driver 575.64.05 / CUDA 12.9):

```bash
conda create -n vllm-qwen36 python=3.12 -y
conda activate vllm-qwen36

# torch from the cu128 channel. The 575 driver is CUDA 12.9 → it CANNOT run a cu130/CUDA-13 torch
# (cuda.is_available() would be False). cu128 ships sm_120 (Blackwell) and runs on the 575 driver.
pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.11.0 torchvision torchaudio

# vLLM 0.23.0 — the per-CUDA GitHub-release wheel, NOT `pip install vllm`. The PyPI default is a
# CUDA-13 build whose *.so link libcudart.so.13 and need driver ≥580; it fails on the 575 driver.
# The cu129 wheel matches CUDA 12.9 exactly. (There is no cu128 vLLM wheel — only cu129 / cpu / cu13.)
pip install https://github.com/vllm-project/vllm/releases/download/v0.23.0/vllm-0.23.0+cu129-cp38-abi3-manylinux_2_28_x86_64.whl \
    --extra-index-url https://download.pytorch.org/whl/cu128

# transformers 5.x carries the qwen3_5 modeling code (lives in ≥5.3; vLLM 0.20–0.23 exclude 5.0–5.4,
# so the resolver lands on the latest 5.x). Pin for reproducibility:
pip install "transformers==5.12.1"

pip check     # should be clean
```

Verified install (this is what's running): **Python 3.12.13, torch 2.11.0+cu128, vllm 0.23.0+cu129,
transformers 5.12.1.** Sanity check the arch is registered:

```bash
python -c "from vllm.model_executor.models.registry import ModelRegistry; \
print('Qwen3_5ForConditionalGeneration' in ModelRegistry.get_supported_archs())"   # -> True
```

---

## 2. GPU portability — what changes per cluster

The env above is largely portable; two things are tied to the **GPU arch** and the **driver**:

| | build box (this repo) | **H100 cluster (2× H100)** |
|---|---|---|
| GPU / arch | RTX PRO 6000 Blackwell, **sm_120**, ~96 GB | H100, **sm_90**, 80 GB |
| driver / CUDA | 575.64.05 / 12.9 | check `nvidia-smi` |
| vLLM wheel | **cu129** (driver too old for the cu13 PyPI default) | cu129 wheel above works on sm_90 too; *if* the driver is ≥580 (CUDA 13) the plain `pip install vllm==0.23.0` also works |
| `TORCH_CUDA_ARCH_LIST` | `12.0` | **`9.0`** |
| `VLLM_USE_FLASHINFER_SAMPLER` | `0` (a flashinfer JIT-sampler bug on sm_120) | **`1`** (or unset — flashinfer is fine on sm_90) |
| `--max-num-seqs` | `256` | `256` (a *model* property — the hybrid Mamba cache vs CUDA-graph capture; lower it if 80 GB is tight) |

The two arch env vars are read by the drivers and **default to the Blackwell values**; override them on
H100 (examples below). `TORCH_CUDA_ARCH_LIST=12.0` on an H100 would target the wrong arch — always set
`9.0` there. Everything else (`--gpu-memory-utilization 0.85 --max-model-len 32768`) is unchanged.

Manual serve command (one replica per GPU):

```bash
HF_HOME=/path/to/hf-cache TORCH_CUDA_ARCH_LIST=9.0 VLLM_USE_FLASHINFER_SAMPLER=1 \
CUDA_VISIBLE_DEVICES=0 /path/to/envs/vllm-qwen36/bin/vllm serve Qwen/Qwen3.6-27B-FP8 \
  --port 8000 --gpu-memory-utilization 0.85 --max-model-len 32768 --max-num-seqs 256
```

Note: Qwen3.6 "thinking" is emitted as **plaintext prose** (no `<think>` tags); do NOT pass
`--reasoning-parser`. `llm.extract_json` still recovers the trailing JSON.

---

## 3. The model

`Qwen/Qwen3.6-27B-FP8`, ~29 GB of FP8 safetensors. Set `HF_HOME` and let the first serve download it,
or pre-fetch:

```bash
export HF_HOME=/path/to/hf-cache
huggingface-cli download Qwen/Qwen3.6-27B-FP8
```

(On the build box it is cached under `HF_HOME=/mnt/samsung4t/HF_HOME/sem_modelsexport` — a machine-
specific path; the drivers default to it but accept `HF_HOME` as an override.)

## 4. The data

The HealthBench split is reused from the sibling harness and is git-ignored — see
[`data/README.md`](data/README.md). One `curl` fetches it; `src/common.py` finds it automatically.

---

## Continuing the run on a new cluster

The v2 (27B) behavioral run is **partial** — interrupted when a GPU fell off the bus during the
same-input floor (see [`FINDINGS.md`](FINDINGS.md)). What remains: fill the disclosure + age **score
floors** (the metric is now answer-score std-dev) and **6 grade criteria**, then re-analyze + rebuild
the viewer. `common.judge_criterion` is already hardened for those 6.

**Important: the saved progress is git-ignored, so a fresh clone has none of it.** To *continue*
(not restart from scratch) you must copy these from the build box to the new cluster:

```bash
# from the build box, into the same path on the new cluster (over ssh/rsync):
rsync -a experiments/counterfactual-mutation/results/{shortlist.jsonl,sweep,edits_override,\
footprint_v2_qwen3.6-27b-fp8,answers_v2_qwen3.6-27b-fp8,sweep_grades_v2_qwen3.6-27b-fp8} \
  USER@h100-cluster:/path/to/Auto-Health-Bench/experiments/counterfactual-mutation/results/
```

Then on the H100 cluster (env built per §1, model + data present):

```bash
cd experiments/counterfactual-mutation

# both GPUs (run_behavioral_27b.sh is idempotent/resumable: answers skip-existing, grades resume and
# fill the 6, both floors recompute under the score-SD metric, then analyze + build_viewer + teardown):
VLLM_BIN=/path/to/envs/vllm-qwen36/bin/vllm HF_HOME=/path/to/hf-cache \
  TORCH_CUDA_ARCH_LIST=9.0 VLLM_USE_FLASHINFER_SAMPLER=1 \
  ./run_behavioral_27b.sh

# OR a single GPU (just the remaining work — grade resume + both floors + analyze + viewer):
VLLM_BIN=/path/to/envs/vllm-qwen36/bin/vllm HF_HOME=/path/to/hf-cache \
  TORCH_CUDA_ARCH_LIST=9.0 VLLM_USE_FLASHINFER_SAMPLER=1 GPU=0 PORT=8000 \
  ./complete_v2_gpu1.sh
```

Both drivers own the server lifecycle (start → health-wait → run → **always teardown on exit**) and
write into the `v2_qwen3.6-27b-fp8` version dirs by default (`CM_BEHAVIOR_VERSION`). When they finish,
`results/report.md` loses its ⚠ partial-run banner and the floor/net numbers populate.

**Fresh re-run instead (no state transfer)?** Build env + model + data, then
`python3 src/pick.py …` (curates the item set) → `sweep.py` → `footprint.py` → `run_behavioral_27b.sh`.
Caveat: the D2 disclosure edits in `results/edits_override/` are **subagent-authored** and not
auto-regenerable — without copying them, D2 falls back to the lower-quality Qwen prose→data render. So
copying `edits_override/` (and `shortlist.jsonl`, to keep the same item set) is recommended even for a
"re-run".

## Quick reference — driver env knobs

`VLLM_BIN` (path to the qwen36 `vllm`), `HF_HOME`, `GPUS`/`PORTS` (or `GPU`/`PORT`), `GPU_MEM_UTIL`,
`MAX_MODEL_LEN`, `MAX_NUM_SEQS`, `HEALTH_TIMEOUT`, `FLOOR_ITEMS`, `TORCH_CUDA_ARCH_LIST`,
`VLLM_USE_FLASHINFER_SAMPLER`, `CM_BEHAVIOR_VERSION` (default `v2_qwen3.6-27b-fp8`), `CM_FOOTPRINT_DIR`,
`CM_KEEP_SERVERS=1`, `CM_REUSE=1`. The 4B path is `run_full.sh` (pinned to the `*_v1_qwen3-4b` dirs).
