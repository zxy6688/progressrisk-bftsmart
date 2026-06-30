#!/usr/bin/env bash
# ProgressRisk BFT-SMaRt v2.0 membership-handoff microbenchmark.
# Measures a single committee's real 4 -> 5 -> 4 membership cycle and a matched no-op control.
set -euo pipefail

: "${BFTSMART_HOME:?Set BFTSMART_HOME to an official bft-smart/library v2.0 checkout}"
: "${RESULTS_DIR:=./bftsmart_handoff_results}"
: "${TRIALS:=1}"
: "${STATE_SIZES:=1048576}"
: "${PROBE_SECONDS:=30}"
: "${WARMUP_SECONDS:=4}"
: "${VIEW_TIMEOUT_SECONDS:=30}"
: "${PORT_BASE:=21000}"
: "${SKIP_BUILD:=0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAVA_SRC="$ROOT/production/java"
mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"
[[ -x "$BFTSMART_HOME/gradlew" ]] || { echo "BFTSMART_HOME must point to BFT-SMaRt v2.0" >&2; exit 2; }

ACTIVE_PIDS=()
cleanup_all() {
  local pid
  for pid in "${ACTIVE_PIDS[@]:-}"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "${ACTIVE_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
  ACTIVE_PIDS=()
}
trap cleanup_all EXIT INT TERM

wait_log() {
  local logfile="$1" regex="$2" timeout="$3" start="$SECONDS"
  until grep -Eq "$regex" "$logfile" 2>/dev/null; do
    (( SECONDS - start <= timeout )) || { echo "Timed out waiting for '$regex' in $logfile" >&2; return 1; }
    sleep 0.2
  done
}

wait_view_count() {
  local logfile="$1" min_count="$2" timeout="$3" start="$SECONDS" count
  while true; do
    count=$(grep -c 'New view:' "$logfile" 2>/dev/null || true)
    (( count >= min_count )) && return 0
    (( SECONDS - start <= timeout )) || { echo "Timed out waiting for view $min_count in $logfile" >&2; return 1; }
    sleep 0.2
  done
}

classpath_for() {
  find "$1" -type f -name '*.jar' -print0 | tr '\0' ':' | sed 's/:$//'
}

set_property() {
  local file="$1" key="$2" value="$3"
  if grep -Eq "^[[:space:]]*${key//./\\.}[[:space:]]*=" "$file"; then
    sed -Ei "s|^[[:space:]]*${key//./\\.}[[:space:]]*=.*|${key} = ${value}|" "$file"
  else
    printf '\n%s = %s\n' "$key" "$value" >> "$file"
  fi
}

configure_runtime() {
  local dir="$1" base="$2"
  rm -f "$dir/config/currentView"
  cat > "$dir/config/hosts.config" <<HOSTS
# id address client-to-replica-port replica-to-replica-port
0 127.0.0.1 $((base + 0))  $((base + 1))
1 127.0.0.1 $((base + 10)) $((base + 11))
2 127.0.0.1 $((base + 20)) $((base + 21))
3 127.0.0.1 $((base + 30)) $((base + 31))
4 127.0.0.1 $((base + 40)) $((base + 41))
HOSTS
  set_property "$dir/config/system.config" system.communication.defaultkeys true
  set_property "$dir/config/system.config" system.communication.useSignatures 0
  set_property "$dir/config/system.config" system.servers.num 4
  set_property "$dir/config/system.config" system.servers.f 1
  set_property "$dir/config/system.config" system.initial.view 0,1,2,3
  set_property "$dir/config/system.config" system.totalordermulticast.checkpoint_period 16
  set_property "$dir/config/system.config" system.client.invokeOrderedTimeout 5
}

LAST_PID=''
start_java() {
  local workdir="$1" logfile="$2"; shift 2
  (
    cd "$workdir"
    exec java -cp "$CLASSPATH" "$@"
  ) > "$logfile" 2>&1 &
  LAST_PID=$!
  ACTIVE_PIDS+=("$LAST_PID")
}

propagate_view() {
  local from="$1" trial_root="$2" output="$3" start end view
  start=$(date +%s%N)
  view="$from/config/currentView"
  [[ -f "$view" ]] || { echo "currentView missing at $view" >&2; return 1; }
  for target in "$trial_root"/replica{0,1,2,3,4} "$trial_root"/client "$trial_root"/ttp; do
    cp "$view" "$target/config/currentView"
  done
  end=$(date +%s%N)
  echo "$start,$end" >> "$output"
}

stop_pids() {
  local pid
  for pid in "$@"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "$@"; do wait "$pid" 2>/dev/null || true; done
}

run_mode() {
  local mode="$1" state_bytes="$2" trial="$3" trial_root="$4" dist="$5" summary="$6" base="$7"
  local runtime="$trial_root/$mode"
  mkdir -p "$runtime"
  local who
  for who in replica0 replica1 replica2 replica3 replica4 client ttp; do
    mkdir -p "$runtime/$who"
    cp -a "$dist/." "$runtime/$who/"
    configure_runtime "$runtime/$who" "$base"
  done

  mkdir -p "$runtime/classes"
  local base_cp
  base_cp="$(classpath_for "$runtime/replica0")"
  javac -cp "$base_cp" -d "$runtime/classes" "$JAVA_SRC/StatefulCounterServer.java" "$JAVA_SRC/HandoffProbeClient.java"
  CLASSPATH="$runtime/classes:$base_cp"

  local server_pids=() id pid
  for id in 0 1 2 3; do
    start_java "$runtime/replica$id" "$runtime/replica${id}.log" progressrisk.bftsmart.StatefulCounterServer "$id" "$state_bytes"
    pid="$LAST_PID"
    server_pids+=("$pid")
  done
  for id in 0 1 2 3; do
    wait_log "$runtime/replica${id}.log" 'STATEFUL_COUNTER_READY' "$VIEW_TIMEOUT_SECONDS"
  done

  local probe="$runtime/probe.csv"
  local probe_pid
  start_java "$runtime/client" "$runtime/client.log" progressrisk.bftsmart.HandoffProbeClient 1001 1 "$PROBE_SECONDS" "$probe" 10
  probe_pid="$LAST_PID"
  sleep "$WARMUP_SECONDS"
  wait_log "$runtime/replica0.log" 'STATEFUL_COUNTER_FIRST_ORDERED' "$VIEW_TIMEOUT_SECONDS"

  local ts="$runtime/timestamps.csv" prop="$runtime/view_propagation.csv"
  printf 'event,wall_ns\n' > "$ts"
  printf 'start_ns,end_ns\n' > "$prop"
  local transfer_bytes='' transfer_counter='' transfer_operations='' replica4_pid=''

  if [[ "$mode" == "reconfig" ]]; then
    start_java "$runtime/replica4" "$runtime/replica4.log" progressrisk.bftsmart.StatefulCounterServer 4 "$state_bytes"
    replica4_pid="$LAST_PID"
    server_pids+=("$replica4_pid")
    wait_log "$runtime/replica4.log" 'Waiting for the TTP' "$VIEW_TIMEOUT_SECONDS"

    local t_cmd_add t_view_add t_ready_add t_cmd_remove t_view_final transfer_line
    t_cmd_add=$(date +%s%N); echo "t_cmd_add,$t_cmd_add" >> "$ts"
    (cd "$runtime/ttp" && ./smartrun.sh bftsmart.reconfiguration.util.DefaultVMServices 4 127.0.0.1 "$((base + 40))" "$((base + 41))") > "$runtime/add.log" 2>&1
    for id in 0 1 2 3; do wait_view_count "$runtime/replica${id}.log" 1 "$VIEW_TIMEOUT_SECONDS"; done
    t_view_add=$(date +%s%N); echo "t_view_add,$t_view_add" >> "$ts"
    propagate_view "$runtime/ttp" "$runtime" "$prop"

    wait_log "$runtime/replica4.log" 'STATEFUL_COUNTER_READY' "$VIEW_TIMEOUT_SECONDS"
    wait_log "$runtime/replica4.log" 'STATE_TRANSFER_INSTALLED .*operations=[1-9][0-9]*' "$VIEW_TIMEOUT_SECONDS"
    transfer_line=$(grep -E 'STATE_TRANSFER_INSTALLED .*operations=[1-9][0-9]*' "$runtime/replica4.log" | tail -n 1)
    transfer_bytes=$(sed -nE 's/.*payload_bytes=([0-9]+).*/\1/p' <<<"$transfer_line")
    transfer_counter=$(sed -nE 's/.*counter=([0-9]+).*/\1/p' <<<"$transfer_line")
    transfer_operations=$(sed -nE 's/.*operations=([0-9]+).*/\1/p' <<<"$transfer_line")
    [[ "$transfer_bytes" == "$state_bytes" ]] || { echo "state-transfer payload mismatch: expected $state_bytes, saw $transfer_bytes" >&2; return 1; }
    t_ready_add=$(date +%s%N); echo "t_ready_add,$t_ready_add" >> "$ts"

    t_cmd_remove=$(date +%s%N); echo "t_cmd_remove,$t_cmd_remove" >> "$ts"
    (cd "$runtime/ttp" && ./smartrun.sh bftsmart.reconfiguration.util.DefaultVMServices 4) > "$runtime/remove.log" 2>&1
    for id in 0 1 2 3; do wait_view_count "$runtime/replica${id}.log" 2 "$VIEW_TIMEOUT_SECONDS"; done
    t_view_final=$(date +%s%N); echo "t_view_final,$t_view_final" >> "$ts"
    propagate_view "$runtime/ttp" "$runtime" "$prop"
  else
    echo "control_start,$(date +%s%N)" >> "$ts"
    sleep 4
    echo "control_end,$(date +%s%N)" >> "$ts"
  fi

  wait "$probe_pid" || true
  stop_pids "${server_pids[@]}"
  ACTIVE_PIDS=()

  python3 - "$probe" "$ts" "$prop" "$summary" "$mode" "$state_bytes" "$trial" "$transfer_bytes" "$transfer_counter" "$transfer_operations" <<'PY'
import csv, sys
from pathlib import Path
probe_path, ts_path, prop_path, summary_path = map(Path, sys.argv[1:5])
mode, state_bytes, trial, transfer_bytes, transfer_counter, transfer_operations = sys.argv[5:]
ts = {r['event']: int(r['wall_ns']) for r in csv.DictReader(ts_path.open())}
probe_rows = list(csv.DictReader(probe_path.open())) if probe_path.exists() else []
ok = [r for r in probe_rows if r.get('ok','').lower() == 'true']
fail = [r for r in probe_rows if r.get('ok','').lower() != 'true']
ends = sorted(int(r['end_epoch_ns']) for r in ok)
gap_ms = max((b-a for a,b in zip(ends, ends[1:])), default=0) / 1e6
prop_rows = list(csv.DictReader(prop_path.open())) if prop_path.exists() else []
prop_ms = sum(int(r['end_ns'])-int(r['start_ns']) for r in prop_rows) / 1e6
resume = ''
if 't_view_final' in ts:
    after = [int(r['end_epoch_ns']) for r in ok if int(r['end_epoch_ns']) >= ts['t_view_final']]
    resume = min(after) if after else ''
def ms(a,b): return '' if a not in ts or b not in ts else (ts[b]-ts[a])/1e6
row = [mode, state_bytes, trial, ts.get('t_cmd_add',''), ts.get('t_view_add',''), ts.get('t_ready_add',''), ts.get('t_cmd_remove',''), ts.get('t_view_final',''), resume, ms('t_cmd_add','t_view_add'), ms('t_cmd_add','t_ready_add'), ms('t_cmd_remove','t_view_final'), '' if not resume or 't_cmd_add' not in ts else (int(resume)-ts['t_cmd_add'])/1e6, prop_ms, gap_ms, len(ok), len(fail), transfer_bytes, transfer_counter, transfer_operations]
with summary_path.open('a', newline='') as f: csv.writer(f).writerow(row)
PY
}

write_runner_metadata() {
  {
    echo "captured_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "bftsmart_ref=$(git -C "$BFTSMART_HOME" rev-parse HEAD 2>/dev/null || true)"
    echo "trials=$TRIALS"; echo "state_sizes=$STATE_SIZES"
    echo "probe_seconds=$PROBE_SECONDS"; echo "warmup_seconds=$WARMUP_SECONDS"
    echo "view_timeout_seconds=$VIEW_TIMEOUT_SECONDS"; echo "port_base=$PORT_BASE"
  } > "$RESULTS_DIR/runner_metadata.txt"
}

cd "$BFTSMART_HOME"
if [[ "$SKIP_BUILD" != "1" ]]; then ./gradlew installDist; fi
DIST="$BFTSMART_HOME/build/install/library"
[[ -d "$DIST" ]] || { echo "build/install/library missing after installDist" >&2; exit 2; }
write_runner_metadata
SUMMARY="$RESULTS_DIR/summary.csv"
echo 'mode,state_bytes,trial,t_cmd_add_ns,t_view_add_ns,t_state_ready_ns,t_cmd_remove_ns,t_view_final_ns,t_resume_ns,t_add_view_ms,t_state_ready_ms,t_remove_view_ms,t_cycle_resume_ms,t_view_propagation_ms,longest_reply_gap_ms,probe_successes,probe_failures,state_transfer_payload_bytes,state_transfer_counter,state_transfer_operations' > "$SUMMARY"
IFS=',' read -ra STATES <<< "$STATE_SIZES"
state_index=0
for state_bytes in "${STATES[@]}"; do
  ((state_index+=1))
  for ((trial=1; trial<=TRIALS; trial++)); do
    trial_root="$RESULTS_DIR/state_${state_bytes}/trial_${trial}"
    rm -rf "$trial_root"; mkdir -p "$trial_root"
    no_op_base=$((PORT_BASE + state_index * 10000 + trial * 100))
    reconfig_base=$((no_op_base + 1000))
    run_mode no_op "$state_bytes" "$trial" "$trial_root" "$DIST" "$SUMMARY" "$no_op_base"
    run_mode reconfig "$state_bytes" "$trial" "$trial_root" "$DIST" "$SUMMARY" "$reconfig_base"
  done
done
python3 "$ROOT/production/analyze_bftsmart_handoff.py" "$SUMMARY" "$RESULTS_DIR"
python3 "$ROOT/production/validate_bftsmart_handoff.py" "$SUMMARY" "$RESULTS_DIR" --expected-trials "$TRIALS" --expected-states "$STATE_SIZES"
echo "Completed. Raw data and summary: $RESULTS_DIR"
