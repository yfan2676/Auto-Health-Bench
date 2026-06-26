#!/usr/bin/env bash
#
# run_replication.sh — one-command driver for the counterfactual-replication experiment.
# Serves Qwen3.6-27B-FP8 as BOTH answerer and judge across ALL FOUR H200 GPUs (one replica per
# GPU), then runs the pipeline: sample -> answers (ALL generation) -> grade (ALL grading) ->
# analyze -> build_viewer. Both roles run with thinking on at Qwen3's recommended sampling
# (temp 0.6, top_p 0.95, top_k 20, min_p 0). The servers are ALWAYS torn down on exit (success,
# failed step, or Ctrl-C) via `trap ... EXIT`, so the GPUs never stay occupied.
#
# "Generate everything, then grade everything" is enforced by running answers.py to completion
# before grade.py. Every step is resumable (skip-existing), so a re-run continues where it left off.
#
# Usage:
#   cd experiments/counterfactual-replication
#   ./run_replication.sh
#   CR_RUNS=1 CR_PER_DIM=2 ./run_replication.sh        # quick end-to-end smoke test
#
# Tunables (env): VLLM_BIN, PY, MODEL, HF_HOME, GPUS/PORTS, GPU_MEM_UTIL, MAX_MODEL_LEN,
#   MAX_NUM_SEQS, HEALTH_TIMEOUT, CR_RUNS, CR_PER_DIM, CR_SEED, CR_VERSION, CM_KEEP_SERVERS=1,
#   CM_REUSE=1, HB_MAX_TOKENS.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- config (Qwen3.6-27B-FP8 on the 4x H200 box) -----------------------------
VLLM_BIN="${VLLM_BIN:-/mnt/home/yfan1/miniconda3/envs/timesrl_repro/bin/vllm}"   # vLLM 0.21 + transformers 5.x (qwen3_5 arch)
PY="${PY:-python3}"
MODEL="${MODEL:-Qwen/Qwen3.6-27B-FP8}"
export HF_HOME="${HF_HOME:-/mnt/home/yfan1/hf_home}"   # where the FP8 snapshot is cached
read -ra GPUS  <<< "${GPUS:-0 1 2 3}"
read -ra PORTS <<< "${PORTS:-8000 8001 8002 8003}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-40960}"     # headroom: a long thinking answer + the grader prompt + judge thinking
MAX_NUM_SEQS="${MAX_NUM_SEQS:-256}"         # hybrid Mamba-cache vs CUDA-graph ceiling (model property)
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-1800}"    # 27B FP8 load across 4 GPUs from cache
# H200 is Hopper sm_90 — well-supported, unlike the Blackwell sm_120 box the sibling experiment ran on.
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-9.0}"

LOG="$SCRIPT_DIR/run_replication.log"
SRV_LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$SRV_LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
now() { date '+%Y-%m-%d %H:%M:%S'; }

SERVER_PIDS=()

# --- teardown: ALWAYS stop the servers on exit -------------------------------
_CLEANED=""
cleanup() {
  [ -n "$_CLEANED" ] && return 0
  _CLEANED=1
  echo; echo "########## [$(now)] STOPPING vLLM servers ##########"
  if [ "${CM_KEEP_SERVERS:-0}" = "1" ]; then
    echo "CM_KEEP_SERVERS=1 -> leaving servers up on ports: ${PORTS[*]}"; return 0
  fi
  # Kill ONLY by explicit PID (ours) + any vllm serve bound to our ports. Never a bare `-f`
  # pattern on the model name: this script's own command line would match it and self-kill.
  local targets=() pid p
  for pid in "${SERVER_PIDS[@]:-}"; do [ -n "$pid" ] && targets+=("$pid"); done
  for p in "${PORTS[@]}"; do
    while IFS= read -r pid; do [ -n "$pid" ] && targets+=("$pid"); done \
      < <(pgrep -f "vllm serve.*--port[ =]$p" || true)
  done
  local uniq
  uniq="$(printf '%s\n' "${targets[@]:-}" | grep -E '^[0-9]+$' | sort -u || true)"
  if [ -z "$uniq" ]; then
    echo "no 'vllm serve' processes found on ports ${PORTS[*]}"
  else
    echo "SIGTERM -> $(echo "$uniq" | tr '\n' ' ')"
    echo "$uniq" | xargs -r kill -TERM 2>/dev/null || true
    local i
    for i in $(seq 1 40); do
      nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q . || break
      sleep 1
    done
    local still
    still="$(echo "$uniq" | while read -r pid; do [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && echo "$pid"; done)"
    if [ -n "$still" ]; then
      echo "SIGKILL -> $(echo "$still" | tr '\n' ' ')"; echo "$still" | xargs -r kill -KILL 2>/dev/null || true
    fi
    if nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q .; then
      pgrep -f "VLLM::EngineCore" | xargs -r kill -KILL 2>/dev/null || true; sleep 2
    fi
  fi
  echo "GPU state after teardown:"
  nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- preflight ---------------------------------------------------------------
[ -x "$VLLM_BIN" ] || { echo "ERROR: vLLM binary not found at $VLLM_BIN. Set VLLM_BIN." >&2; exit 1; }
[ -f "$SCRIPT_DIR/results/shortlist.jsonl" ] || { echo "ERROR: results/shortlist.jsonl missing (copy from counterfactual-mutation)." >&2; exit 1; }
[ "${#GPUS[@]}" -eq "${#PORTS[@]}" ] || { echo "ERROR: GPUS/PORTS length mismatch." >&2; exit 1; }

# --- endpoints + harness env (both roles fan across all 4 servers) -----------
urls=""
for p in "${PORTS[@]}"; do urls+="${urls:+,}http://localhost:$p/v1"; done
export HB_BACKEND="${HB_BACKEND:-vllm}"
export HB_TARGET_MODEL="${HB_TARGET_MODEL:-$MODEL}"
export HB_JUDGE_MODEL="${HB_JUDGE_MODEL:-$MODEL}"
export HB_TARGET_BASE_URLS="${HB_TARGET_BASE_URLS:-$urls}"
export HB_JUDGE_BASE_URLS="${HB_JUDGE_BASE_URLS:-$urls}"
export HB_THINK_TARGET="${HB_THINK_TARGET:-1}"
export HB_THINK_JUDGE="${HB_THINK_JUDGE:-1}"           # judge thinks here (NOT held at 0 like the sibling)
export HB_TEMPERATURE="${HB_TEMPERATURE:-0.6}"         # Qwen3 thinking-mode recommended
export HB_TOP_P="${HB_TOP_P:-0.95}"
export HB_MAX_TOKENS="${HB_MAX_TOKENS:-24576}"         # both roles think -> generous headroom
export CM_JUDGE_THINK="${CM_JUDGE_THINK:-1}"
export CM_JUDGE_TEMP="${CM_JUDGE_TEMP:-0.6}"
export CM_TOP_K="${CM_TOP_K:-20}"
export CM_MIN_P="${CM_MIN_P:-0}"
export CR_VERSION="${CR_VERSION:-qwen3.6-27b-fp8-think}"
export CR_RUNS="${CR_RUNS:-3}"
export CR_SEED="${CR_SEED:-20260626}"
export CR_PER_DIM="${CR_PER_DIM:-25}"
# data/ holds a symlink to the shared split; keep CM_DATA_DIR as a fallback to the sibling's copy.
export CM_DATA_DIR="${CM_DATA_DIR:-$SCRIPT_DIR/../counterfactual-mutation/data}"

# --- start the four 27B servers (one per GPU) --------------------------------
start_servers() {
  local i gpu port srv_log
  for i in "${!PORTS[@]}"; do
    gpu="${GPUS[$i]}"; port="${PORTS[$i]}"
    if curl -sf "http://localhost:$port/v1/models" >/dev/null 2>&1; then
      if [ "${CM_REUSE:-0}" = "1" ]; then echo "[:$port] reusing healthy server (CM_REUSE=1)"; continue; fi
      echo "ERROR: a server already listens on :$port. Stop it or set CM_REUSE=1." >&2; exit 1
    fi
    srv_log="$SRV_LOG_DIR/vllm_${port}.log"
    echo "[:$port] starting $MODEL on GPU $gpu  (log: $srv_log)"
    CUDA_VISIBLE_DEVICES="$gpu" \
      nohup "$VLLM_BIN" serve "$MODEL" \
        --port "$port" --gpu-memory-utilization "$GPU_MEM_UTIL" \
        --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
        >"$srv_log" 2>&1 &
    SERVER_PIDS+=("$!")
  done
}

wait_health() {
  local port deadline
  for port in "${PORTS[@]}"; do
    deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
    printf '[:%s] waiting for /v1/models ' "$port"
    until curl -sf "http://localhost:$port/v1/models" >/dev/null 2>&1; do
      if [ "$(date +%s)" -ge "$deadline" ]; then
        echo " TIMEOUT after ${HEALTH_TIMEOUT}s"; echo "--- tail $SRV_LOG_DIR/vllm_${port}.log ---"
        tail -n 40 "$SRV_LOG_DIR/vllm_${port}.log" 2>/dev/null || true; exit 1
      fi
      printf '.'; sleep 5
    done
    echo " up"
  done
}

run_step() {
  local name="$1"; shift; local start_ts rc dur
  start_ts=$(date +%s)
  echo "===== [$(now)] START $name :: $* ====="
  set +e; "$@"; rc=$?; set -e
  dur=$(( $(date +%s) - start_ts ))
  echo "===== [$(now)] END   $name (rc=$rc, ${dur}s) ====="
  if [ "$rc" -ne 0 ]; then echo "!! step '$name' failed (rc=$rc) — aborting; exit trap stops servers."; exit "$rc"; fi
}

# --- run ---------------------------------------------------------------------
echo "########## [$(now)] REPLICATION RUN START (pid $$) ##########"
echo "model=$MODEL  endpoints=$urls  version=$CR_VERSION"
echo "runs=$CR_RUNS  per_dim=$CR_PER_DIM  seed=$CR_SEED  judge_think=$HB_THINK_JUDGE judge_temp=$CM_JUDGE_TEMP"
echo "sampling: temp=$HB_TEMPERATURE top_p=$HB_TOP_P top_k=$CM_TOP_K min_p=$CM_MIN_P  max_tokens=$HB_MAX_TOKENS"

start_servers
wait_health

run_step sample       "$PY" src/sample.py
run_step answers      "$PY" src/answers.py      # ALL generation first, across the 4 GPUs
run_step grade        "$PY" src/grade.py        # THEN all grading, across the 4 GPUs
run_step analyze      "$PY" src/analyze.py
run_step build_viewer "$PY" src/build_viewer.py

echo "########## [$(now)] REPLICATION RUN COMPLETE ##########"
echo "report: results/report.md   viewer: viewer/data.json"
# EXIT trap now stops all servers and frees the GPUs
