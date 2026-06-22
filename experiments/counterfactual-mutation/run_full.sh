#!/usr/bin/env bash
#
# run_full.sh — one-command driver for the counterfactual-mutation pipeline that
# OWNS the vLLM server lifecycle. It starts the two Qwen3-4B servers (one per GPU),
# waits for them to come up, runs the full sweep -> ... -> build_viewer pipeline, and
# then *always* stops the servers again — on success, on a failed step, or on Ctrl-C —
# so the GPUs never sit occupied after a run finishes.
#
# The server teardown is wired to a `trap ... EXIT INT TERM`, so it fires no matter how
# the script exits. Re-creates the runner that produced run_full.log, with the teardown
# added (see this experiment's README "How to run").
#
# Usage:
#   cd experiments/counterfactual-mutation
#   ./run_full.sh                 # start servers, run pipeline, stop servers
#
# Prereqs: results/shortlist.jsonl must already exist (build it once with
#   python3 src/pick.py --limit 100 && python3 src/pick.py --dimension disclosure --limit 71
# — pick curates the item set, so it is intentionally NOT part of the automated run).
#
# Tunable via env (defaults match the proven 2-GPU Blackwell run):
#   VLLM_BIN        vllm binary (default: the conda `vllm` env — it is not on PATH)
#   PY             python for the pipeline steps (default: python3)
#   MODEL          served model id            (default: Qwen/Qwen3-4B)
#   GPUS / PORTS    space-separated, paired    (default: "0 1" / "8000 8001")
#   GPU_MEM_UTIL    --gpu-memory-utilization   (default: 0.85)
#   MAX_MODEL_LEN   --max-model-len            (default: 32768)
#   HEALTH_TIMEOUT  seconds to wait per server (default: 600)
#   CM_RUN_FOOTPRINT=1   also run the (optional) a-priori footprint step
#   CM_KEEP_SERVERS=1    leave the servers running at the end (skip teardown)
#   CM_REUSE=1           reuse a server already healthy on a port instead of erroring
#
set -Eeuo pipefail

# --- locate + enter this experiment directory so all src/... and results/... paths resolve
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- config ------------------------------------------------------------------
VLLM_BIN="${VLLM_BIN:-/home/yuang/miniconda3/envs/vllm/bin/vllm}"
PY="${PY:-python3}"
MODEL="${MODEL:-Qwen/Qwen3-4B}"
read -ra GPUS  <<< "${GPUS:-0 1}"
read -ra PORTS <<< "${PORTS:-8000 8001}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-600}"

LOG="$SCRIPT_DIR/run_full.log"
SRV_LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$SRV_LOG_DIR"

# tee everything (this script + the python steps) to run_full.log
exec > >(tee -a "$LOG") 2>&1

now() { date '+%Y-%m-%d %H:%M:%S'; }

SERVER_PIDS=()   # PIDs of the servers WE started (for teardown); set before the trap can fire

# --- teardown: ALWAYS stop the vLLM servers when the script exits -------------
_CLEANED=""
cleanup() {
  [ -n "$_CLEANED" ] && return 0   # idempotent: EXIT may be reached via INT/TERM
  _CLEANED=1
  echo
  echo "########## [$(now)] STOPPING vLLM servers ##########"
  if [ "${CM_KEEP_SERVERS:-0}" = "1" ]; then
    echo "CM_KEEP_SERVERS=1 -> leaving servers up on ports: ${PORTS[*]}"
    return 0
  fi

  # Collect targets: the PIDs we started + any `vllm serve` bound to our ports
  # (covers reused/pre-existing servers too — the request is that these ports are
  # freed when the run finishes, regardless of who started them).
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
    # vLLM tears down its EngineCore children on SIGTERM; wait for the GPUs to clear.
    local i
    for i in $(seq 1 30); do
      nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q . || break
      sleep 1
    done
    # backstop: hard-kill anything from our list still alive
    local still
    still="$(echo "$uniq" | while read -r pid; do
               [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && echo "$pid"; done)"
    if [ -n "$still" ]; then
      echo "SIGKILL -> $(echo "$still" | tr '\n' ' ')"
      echo "$still" | xargs -r kill -KILL 2>/dev/null || true
    fi
    # last resort: if a GPU is still occupied, kill any orphaned EngineCore worker
    if nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -q .; then
      pgrep -f "VLLM::EngineCore" | xargs -r kill -KILL 2>/dev/null || true
      sleep 2
    fi
  fi
  echo "GPU state after teardown:"
  nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- preflight ---------------------------------------------------------------
[ -x "$VLLM_BIN" ] || VLLM_BIN="$(command -v vllm || true)"
if [ -z "$VLLM_BIN" ] || [ ! -x "$VLLM_BIN" ]; then
  echo "ERROR: vLLM binary not found. Set VLLM_BIN=/path/to/vllm (the conda 'vllm' env)." >&2
  exit 1
fi
if [ ! -f "$SCRIPT_DIR/results/shortlist.jsonl" ]; then
  echo "ERROR: results/shortlist.jsonl not found — build it first with src/pick.py (see header)." >&2
  exit 1
fi
if [ "${#GPUS[@]}" -ne "${#PORTS[@]}" ]; then
  echo "ERROR: GPUS (${GPUS[*]}) and PORTS (${PORTS[*]}) must have the same length." >&2
  exit 1
fi

# --- endpoints + harness env (both roles fan across both servers) ------------
urls=""
for p in "${PORTS[@]}"; do urls+="${urls:+,}http://localhost:$p/v1"; done
export HB_BACKEND="${HB_BACKEND:-vllm}"
export HB_TARGET_MODEL="${HB_TARGET_MODEL:-$MODEL}"
export HB_JUDGE_MODEL="${HB_JUDGE_MODEL:-$MODEL}"
export HB_TARGET_BASE_URLS="${HB_TARGET_BASE_URLS:-$urls}"
export HB_JUDGE_BASE_URLS="${HB_JUDGE_BASE_URLS:-$urls}"
export HB_THINK_JUDGE="${HB_THINK_JUDGE:-0}"      # non-thinking judge ~10x faster
export HB_MAX_TOKENS="${HB_MAX_TOKENS:-16384}"    # long thinking author/answer calls
# This driver serves Qwen3-4B, so it reads/writes the v1 (4B) behavioral + footprint dirs. Without
# this pin the steps default to the NEWEST version dirs (v2 / Qwen3.6-27B) and would clobber the
# 27B results. Override CM_BEHAVIOR_VERSION / CM_FOOTPRINT_DIR to target a different version.
export CM_BEHAVIOR_VERSION="${CM_BEHAVIOR_VERSION:-v1_qwen3-4b}"
export CM_FOOTPRINT_DIR="${CM_FOOTPRINT_DIR:-footprint_v1_qwen3-4b}"

# --- start the servers (one per GPU) -----------------------------------------
start_servers() {
  local i gpu port srv_log
  for i in "${!PORTS[@]}"; do
    gpu="${GPUS[$i]}"; port="${PORTS[$i]}"
    if curl -sf "http://localhost:$port/v1/models" >/dev/null 2>&1; then
      if [ "${CM_REUSE:-0}" = "1" ]; then
        echo "[:$port] reusing server already healthy on this port (CM_REUSE=1)"
        continue
      fi
      echo "ERROR: a server is already listening on :$port. Stop it, or set CM_REUSE=1." >&2
      exit 1
    fi
    srv_log="$SRV_LOG_DIR/vllm_${port}.log"
    echo "[:$port] starting $MODEL on GPU $gpu  (log: $srv_log)"
    CUDA_VISIBLE_DEVICES="$gpu" nohup "$VLLM_BIN" serve "$MODEL" \
      --port "$port" --gpu-memory-utilization "$GPU_MEM_UTIL" \
      --max-model-len "$MAX_MODEL_LEN" >"$srv_log" 2>&1 &
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
        echo " TIMEOUT after ${HEALTH_TIMEOUT}s"
        echo "--- last 30 lines of $SRV_LOG_DIR/vllm_${port}.log ---"
        tail -n 30 "$SRV_LOG_DIR/vllm_${port}.log" 2>/dev/null || true
        exit 1
      fi
      printf '.'
      sleep 3
    done
    echo " up"
  done
}

# --- step runner: logs START/END + rc/duration, aborts (-> trap) on failure --
run_step() {
  local name="$1"; shift
  local start_ts rc dur
  start_ts=$(date +%s)
  echo "===== [$(now)] START $name :: $* ====="
  set +e
  "$@"
  rc=$?
  set -e
  dur=$(( $(date +%s) - start_ts ))
  echo "===== [$(now)] END   $name (rc=$rc, ${dur}s) ====="
  if [ "$rc" -ne 0 ]; then
    echo "!! step '$name' failed (rc=$rc) — aborting run; the exit trap will stop the servers."
    exit "$rc"
  fi
}

# --- run ---------------------------------------------------------------------
echo "########## [$(now)] RUN START  (pid $$) ##########"
"$PY" - <<'PYEOF' || true
import json, collections
c = collections.Counter()
with open("results/shortlist.jsonl") as f:
    for line in f:
        line = line.strip()
        if line:
            c[json.loads(line).get("dimension", "age")] += 1
print("shortlist:", dict(c), "total", sum(c.values()))
PYEOF
echo "endpoints: target/judge -> $urls   (judge_think=$HB_THINK_JUDGE, max_tokens=$HB_MAX_TOKENS)"

start_servers
wait_health

run_step sweep        "$PY" src/sweep.py
[ "${CM_RUN_FOOTPRINT:-0}" = "1" ] && run_step footprint "$PY" src/footprint.py
run_step answers      "$PY" src/answers.py
run_step sweep_grade  "$PY" src/sweep_grade.py
run_step floor_age    "$PY" src/noise_floor.py --dimension age --items 20
run_step floor_disc   "$PY" src/noise_floor.py --dimension disclosure --items 20
run_step analyze      "$PY" src/analyze.py
run_step build_viewer "$PY" src/build_viewer.py

echo "########## [$(now)] RUN COMPLETE ##########"
echo "report: results/report.md   viewer: viewer/data.json (serve: $PY -m http.server -d viewer 8080)"
# the EXIT trap now stops both servers and frees the GPUs
