#!/usr/bin/env bash
#
# run_behavioral_27b.sh — re-run the BEHAVIORAL half of the counterfactual-mutation pipeline
# (fresh answers + their grades + the same-input noise floor) with Qwen3.6-27B-FP8 as BOTH the
# answer model and the judge, then re-analyze and rebuild the viewer.
#
# Unlike run_full.sh (the 4B driver) this script:
#   * serves Qwen3.6-27B-FP8 from the isolated `vllm-qwen36` conda env with the Blackwell sm_120
#     serve fixes (TORCH_CUDA_ARCH_LIST, flashinfer sampler off, --max-num-seqs) — see the memory
#     note vllm-blackwell-env;
#   * does NOT run sweep.py (the mutated inputs are model-independent — we reuse the exact same
#     variants so the 4B-vs-27B comparison is apples-to-apples) and does NOT run footprint.py
#     (the a-priori classifier was already re-run for 27B = footprint_v2);
#   * writes into the v2 behavioral dirs (CM_BEHAVIOR_VERSION defaults to v2_qwen3.6-27b-fp8 in
#     common.py), leaving the v1 (4B) answers/grades/floor untouched.
#
# Server lifecycle is owned here: it starts the two servers, waits for health, runs the steps,
# and ALWAYS stops the servers on exit (success, failed step, or Ctrl-C) via `trap ... EXIT`.
#
# Usage:
#   cd experiments/counterfactual-mutation
#   ./run_behavioral_27b.sh
#
# Tunables (env, defaults match the proven 2-GPU Blackwell 27B serve):
#   VLLM_BIN, MODEL, HF_HOME, GPUS/PORTS, GPU_MEM_UTIL, MAX_MODEL_LEN, MAX_NUM_SEQS,
#   HEALTH_TIMEOUT, FLOOR_ITEMS (items/dim for noise_floor), CM_KEEP_SERVERS=1, CM_REUSE=1
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- config (Qwen3.6-27B-FP8 on the Blackwell box) ---------------------------
VLLM_BIN="${VLLM_BIN:-/home/yuang/miniconda3/envs/vllm-qwen36/bin/vllm}"
PY="${PY:-python3}"
MODEL="${MODEL:-Qwen/Qwen3.6-27B-FP8}"
export HF_HOME="${HF_HOME:-/mnt/samsung4t/HF_HOME/sem_modelsexport}"   # where the FP8 snapshot is cached
read -ra GPUS  <<< "${GPUS:-0 1}"
read -ra PORTS <<< "${PORTS:-8000 8001}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-256}"        # hybrid Mamba-cache vs CUDA-graph ceiling (default 1024 fails)
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-1200}"   # 27B FP8 load is slower than the 4B
FLOOR_ITEMS="${FLOOR_ITEMS:-20}"           # items/dimension for the same-input floor (matches v1)

LOG="$SCRIPT_DIR/run_behavioral_27b.log"
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
[ -x "$VLLM_BIN" ] || { echo "ERROR: vLLM binary not found at $VLLM_BIN (the vllm-qwen36 env)." >&2; exit 1; }
[ -f "$SCRIPT_DIR/results/shortlist.jsonl" ] || { echo "ERROR: results/shortlist.jsonl missing." >&2; exit 1; }
[ "${#GPUS[@]}" -eq "${#PORTS[@]}" ] || { echo "ERROR: GPUS/PORTS length mismatch." >&2; exit 1; }

# --- endpoints + harness env (both roles fan across both 27B servers) --------
urls=""
for p in "${PORTS[@]}"; do urls+="${urls:+,}http://localhost:$p/v1"; done
export HB_BACKEND="${HB_BACKEND:-vllm}"
export HB_TARGET_MODEL="${HB_TARGET_MODEL:-$MODEL}"
export HB_JUDGE_MODEL="${HB_JUDGE_MODEL:-$MODEL}"
export HB_TARGET_BASE_URLS="${HB_TARGET_BASE_URLS:-$urls}"
export HB_JUDGE_BASE_URLS="${HB_JUDGE_BASE_URLS:-$urls}"
export HB_THINK_JUDGE="${HB_THINK_JUDGE:-0}"      # non-thinking judge ~10x faster
export HB_MAX_TOKENS="${HB_MAX_TOKENS:-20480}"    # long thinking answer calls need headroom
# Behavioral version dirs default to v2 (Qwen3.6-27B) in common.py — answers/grades/floor go to
# results/{answers,sweep_grades}_v2_qwen3.6-27b-fp8/ + noise_floor_v2_qwen3.6-27b-fp8.json.
export CM_BEHAVIOR_VERSION="${CM_BEHAVIOR_VERSION:-v2_qwen3.6-27b-fp8}"
export CM_FOOTPRINT_DIR="${CM_FOOTPRINT_DIR:-footprint_v2_qwen3.6-27b-fp8}"   # 27B classifier (already run)

# --- start the two 27B servers (one per GPU) with the Blackwell sm_120 fixes -
start_servers() {
  local i gpu port srv_log
  for i in "${!PORTS[@]}"; do
    gpu="${GPUS[$i]}"; port="${PORTS[$i]}"
    if curl -sf "http://localhost:$port/v1/models" >/dev/null 2>&1; then
      if [ "${CM_REUSE:-0}" = "1" ]; then echo "[:$port] reusing healthy server (CM_REUSE=1)"; continue; fi
      echo "ERROR: a server already listens on :$port. Stop it or set CM_REUSE=1." >&2; exit 1
    fi
    srv_log="$SRV_LOG_DIR/vllm27b_${port}.log"
    echo "[:$port] starting $MODEL on GPU $gpu  (log: $srv_log)"
    CUDA_VISIBLE_DEVICES="$gpu" \
      TORCH_CUDA_ARCH_LIST=12.0 \
      VLLM_USE_FLASHINFER_SAMPLER=0 \
      nohup "$VLLM_BIN" serve "$MODEL" \
        --port "$port" --gpu-memory-utilization "$GPU_MEM_UTIL" \
        --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" \
        >"$srv_log" 2>&1 &
    SERVER_PIDS+=("$!")
  done
  printf '%s\n' "${SERVER_PIDS[@]}" > /tmp/qwen36_behavioral_pids
}

wait_health() {
  local port deadline
  for port in "${PORTS[@]}"; do
    deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
    printf '[:%s] waiting for /v1/models ' "$port"
    until curl -sf "http://localhost:$port/v1/models" >/dev/null 2>&1; do
      if [ "$(date +%s)" -ge "$deadline" ]; then
        echo " TIMEOUT after ${HEALTH_TIMEOUT}s"; echo "--- tail $SRV_LOG_DIR/vllm27b_${port}.log ---"
        tail -n 40 "$SRV_LOG_DIR/vllm27b_${port}.log" 2>/dev/null || true; exit 1
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
echo "########## [$(now)] BEHAVIORAL-27B RUN START (pid $$) ##########"
echo "model=$MODEL  endpoints=$urls  behavior_version=$CM_BEHAVIOR_VERSION  footprint=$CM_FOOTPRINT_DIR"
echo "judge_think=$HB_THINK_JUDGE  max_tokens=$HB_MAX_TOKENS  floor_items/dim=$FLOOR_ITEMS"

start_servers
wait_health

run_step answers      "$PY" src/answers.py
run_step sweep_grade  "$PY" src/sweep_grade.py
run_step floor_age    "$PY" src/noise_floor.py --dimension age --items "$FLOOR_ITEMS"
run_step floor_disc   "$PY" src/noise_floor.py --dimension disclosure --items "$FLOOR_ITEMS"
run_step analyze      "$PY" src/analyze.py
run_step build_viewer "$PY" src/build_viewer.py

echo "########## [$(now)] BEHAVIORAL-27B RUN COMPLETE ##########"
echo "report: results/report.md   viewer: viewer/data.json"
# EXIT trap now stops both servers and frees the GPUs
