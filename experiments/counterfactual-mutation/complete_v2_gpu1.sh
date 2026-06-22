#!/usr/bin/env bash
#
# complete_v2_gpu1.sh — finish the v2 (Qwen3.6-27B-FP8) behavioral run on a SINGLE GPU after
# GPU 0 fell off the bus mid-run. Brings up one 27B server on GPU 1 / :8001 and runs only the
# work the main run left unfinished:
#   1. sweep_grade.py (resume) — fills the 6 criteria the judge left ungraded (now with the
#      hardened grader-JSON extraction + think-on rescue in common.judge_criterion);
#   2. noise_floor.py --dimension disclosure — the floor the GPU-0 fault interrupted (merges into
#      the existing noise_floor_v2 json, which already holds the age floor);
#   3. analyze.py + build_viewer.py — regenerate metrics/report/viewer from the now-complete v2.
# Does NOT touch answers (171/171 done) or the age floor (done). ALWAYS stops the server on exit.
#
# Usage:  cd experiments/counterfactual-mutation && ./complete_v2_gpu1.sh
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$SCRIPT_DIR"

VLLM_BIN="${VLLM_BIN:-/home/yuang/miniconda3/envs/vllm-qwen36/bin/vllm}"
PY="${PY:-python3}"
MODEL="${MODEL:-Qwen/Qwen3.6-27B-FP8}"
export HF_HOME="${HF_HOME:-/mnt/samsung4t/HF_HOME/sem_modelsexport}"
GPU="${GPU:-1}"; PORT="${PORT:-8001}"          # GPU 0 is offline — single replica on GPU 1
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"; MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"; MAX_NUM_SEQS="${MAX_NUM_SEQS:-256}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-1200}"; FLOOR_ITEMS="${FLOOR_ITEMS:-20}"
GRADES_DIR="results/sweep_grades_v2_qwen3.6-27b-fp8"

LOG="$SCRIPT_DIR/complete_v2_gpu1.log"; SRV_LOG_DIR="$SCRIPT_DIR/logs"; mkdir -p "$SRV_LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
now() { date '+%Y-%m-%d %H:%M:%S'; }
SERVER_PID=""

_CLEANED=""
cleanup() {
  [ -n "$_CLEANED" ] && return 0; _CLEANED=1
  echo; echo "########## [$(now)] STOPPING vLLM server ##########"
  [ "${CM_KEEP_SERVERS:-0}" = "1" ] && { echo "CM_KEEP_SERVERS=1 -> leaving up :$PORT"; return 0; }
  # Explicit PID(s) only — never `pkill -f <pattern>` (this script's own cmdline would match -> self-kill).
  local targets=() pid
  [ -n "$SERVER_PID" ] && targets+=("$SERVER_PID")
  while IFS= read -r pid; do [ -n "$pid" ] && targets+=("$pid"); done < <(pgrep -f "vllm serve.*--port[ =]$PORT" || true)
  local uniq; uniq="$(printf '%s\n' "${targets[@]:-}" | grep -E '^[0-9]+$' | sort -u || true)"
  if [ -z "$uniq" ]; then echo "no vllm serve on :$PORT"; else
    echo "SIGTERM -> $(echo "$uniq" | tr '\n' ' ')"; echo "$uniq" | xargs -r kill -TERM 2>/dev/null || true
    local i; for i in $(seq 1 40); do nvidia-smi --id="$GPU" --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q . || break; sleep 1; done
    local still; still="$(echo "$uniq" | while read -r pid; do [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && echo "$pid"; done)"
    [ -n "$still" ] && { echo "SIGKILL -> $still"; echo "$still" | xargs -r kill -KILL 2>/dev/null || true; }
  fi
  echo "GPU $GPU state after teardown:"; nvidia-smi --id="$GPU" --query-gpu=index,memory.used,memory.total --format=csv 2>/dev/null || true
}
trap cleanup EXIT; trap 'exit 130' INT; trap 'exit 143' TERM

[ -x "$VLLM_BIN" ] || { echo "ERROR: vLLM bin not found at $VLLM_BIN" >&2; exit 1; }

export HB_BACKEND=vllm HB_TARGET_MODEL="$MODEL" HB_JUDGE_MODEL="$MODEL"
export HB_TARGET_BASE_URLS="http://localhost:$PORT/v1" HB_JUDGE_BASE_URLS="http://localhost:$PORT/v1"
export HB_THINK_JUDGE="${HB_THINK_JUDGE:-0}" HB_MAX_TOKENS="${HB_MAX_TOKENS:-20480}"
export CM_BEHAVIOR_VERSION="${CM_BEHAVIOR_VERSION:-v2_qwen3.6-27b-fp8}"
export CM_FOOTPRINT_DIR="${CM_FOOTPRINT_DIR:-footprint_v2_qwen3.6-27b-fp8}"

run_step() {
  local name="$1"; shift; local s rc d; s=$(date +%s)
  echo "===== [$(now)] START $name :: $* ====="
  set +e; "$@"; rc=$?; set -e
  d=$(( $(date +%s) - s )); echo "===== [$(now)] END   $name (rc=$rc, ${d}s) ====="
  [ "$rc" -ne 0 ] && { echo "!! step '$name' failed (rc=$rc) — aborting; exit trap stops the server."; exit "$rc"; }
}

echo "########## [$(now)] COMPLETE-V2 (single GPU $GPU) START (pid $$) ##########"
echo "model=$MODEL  endpoint=http://localhost:$PORT/v1  floor_items=$FLOOR_ITEMS"

if curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; then
  echo "[:$PORT] reusing healthy server"
else
  srv_log="$SRV_LOG_DIR/vllm27b_${PORT}.log"
  echo "[:$PORT] starting $MODEL on GPU $GPU (log: $srv_log)"
  CUDA_VISIBLE_DEVICES="$GPU" TORCH_CUDA_ARCH_LIST=12.0 VLLM_USE_FLASHINFER_SAMPLER=0 \
    nohup "$VLLM_BIN" serve "$MODEL" --port "$PORT" --gpu-memory-utilization "$GPU_MEM_UTIL" \
      --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS" >"$srv_log" 2>&1 &
  SERVER_PID="$!"
  deadline=$(( $(date +%s) + HEALTH_TIMEOUT )); printf '[:%s] waiting ' "$PORT"
  until curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; do
    [ "$(date +%s)" -ge "$deadline" ] && { echo " TIMEOUT"; tail -n 40 "$srv_log" 2>/dev/null; exit 1; }
    printf '.'; sleep 5
  done; echo " up"
fi

run_step grade_resume "$PY" src/sweep_grade.py
run_step floor_disc   "$PY" src/noise_floor.py --dimension disclosure --items "$FLOOR_ITEMS"
run_step analyze      "$PY" src/analyze.py
run_step build_viewer "$PY" src/build_viewer.py
echo "########## [$(now)] COMPLETE-V2 DONE ##########"
