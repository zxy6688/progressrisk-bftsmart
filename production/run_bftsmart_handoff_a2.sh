#!/usr/bin/env bash
# A2: one real BFT-SMaRt v2.0 stateful membership handoff.
#
# This script is intentionally a single 4 -> 5 -> 4 gate, not a benchmark.
# It is allowed to run only after A0 (official Counter) and A1 (project
# stateful service + snapshot) passed. The success condition is exact:
#   (i) all four initial replicas serve three ordered writes;
#  (ii) a pre-started replica 4 joins view 1 and installs transferred state;
# (iii) fresh client using view 1 observes counter 4;
#  (iv) replica 0 is removed, survivors install view 2 {1,2,3,4};
#   (v) fresh client using view 2 observes counter 5.
set -Eeuo pipefail

: "${BFTSMART_HOME:?Set BFTSMART_HOME to a BFT-SMaRt v2.0 checkout}"
: "${RESULTS_DIR:=./bftsmart_handoff_a2}"
: "${SNAPSHOT_BYTES:=1048576}"
: "${READY_TIMEOUT_SECONDS:=150}"
: "${PHASE_TIMEOUT_SECONDS:=180}"
: "${COMMAND_TIMEOUT_SECONDS:=75}"
: "${PORT_BASE:=22000}"
: "${SKIP_BUILD:=0}"

for integer_name in SNAPSHOT_BYTES READY_TIMEOUT_SECONDS PHASE_TIMEOUT_SECONDS COMMAND_TIMEOUT_SECONDS PORT_BASE SKIP_BUILD; do
  value="${!integer_name}"
  case "$value" in
    ''|*[!0-9]*) echo "$integer_name must be a nonnegative integer" >&2; exit 2 ;;
  esac
done
(( SNAPSHOT_BYTES >= 0 )) || { echo 'SNAPSHOT_BYTES must be >= 0' >&2; exit 2; }
(( READY_TIMEOUT_SECONDS >= 1 && PHASE_TIMEOUT_SECONDS >= 1 && COMMAND_TIMEOUT_SECONDS >= 1 )) || {
  echo 'timeouts must be >= 1' >&2; exit 2;
}
(( PORT_BASE >= 1024 && PORT_BASE + 41 <= 65535 )) || { echo 'PORT_BASE must leave room for five replica port pairs' >&2; exit 2; }
(( SKIP_BUILD == 0 || SKIP_BUILD == 1 )) || { echo 'SKIP_BUILD must be 0 or 1' >&2; exit 2; }
[[ -x "$BFTSMART_HOME/gradlew" ]] || { echo "BFTSMART_HOME is not a BFT-SMaRt checkout: $BFTSMART_HOME" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SOURCE="$ROOT_DIR/production/java"
for required in StatefulCounterServer.java HandoffSequenceClient.java ViewInspector.java; do
  [[ -f "$APP_SOURCE/$required" ]] || { echo "missing Java source: $APP_SOURCE/$required" >&2; exit 2; }
done

mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"
LOGS="$RESULTS_DIR/logs"
RUNTIME="$RESULTS_DIR/runtime"
APP_BUILD="$RESULTS_DIR/app_build"
VERDICT="$RESULTS_DIR/verdict.txt"
METRICS="$RESULTS_DIR/metrics.tsv"

now_ms() { date +%s%3N; }

# Track the actual exec'd Java processes. This is important: killing the shell
# wrapper is not sufficient to release BFT-SMaRt listener ports.
declare -A replica_pid=()
all_pids=()
cleanup() {
  local pid
  for pid in "${all_pids[@]:-}"; do kill -TERM "$pid" 2>/dev/null || true; done
  sleep 0.5 || true
  for pid in "${all_pids[@]:-}"; do kill -KILL "$pid" 2>/dev/null || true; done
  for pid in "${all_pids[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

fail() {
  echo "FAIL: $*" >&2
  printf 'A2_HANDOFF_FAIL\nreason=%s\n' "$*" > "$VERDICT"
  exit 1
}

wait_marker() {
  local label="$1" marker="$2" logfile="$3" pid="$4" timeout_seconds="$5"
  local start="$SECONDS"
  while ! grep -Fq "$marker" "$logfile" 2>/dev/null; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Process for $label exited before marker: $marker" >&2
      tail -n 220 "$logfile" >&2 || true
      return 1
    fi
    if (( SECONDS - start >= timeout_seconds )); then
      echo "Timed out waiting for $label marker: $marker" >&2
      tail -n 220 "$logfile" >&2 || true
      return 1
    fi
    sleep 0.25
  done
}

view_matches() {
  local current_view="$1" expected_id="$2" expected_members="$3"
  [[ -s "$current_view" ]] || return 1
  java -cp "$APP_JAR:$DIST/lib/*" progressrisk.bftsmart.ViewInspector \
    "$current_view" "$expected_id" "$expected_members" >/dev/null 2>&1
}

wait_views() {
  local label="$1" expected_id="$2" expected_members="$3"
  shift 3
  local start="$SECONDS" role complete
  while true; do
    complete=1
    for role in "$@"; do
      if ! view_matches "$RUNTIME/$role/config/currentView" "$expected_id" "$expected_members"; then
        complete=0
        break
      fi
    done
    (( complete == 1 )) && return 0
    if (( SECONDS - start >= PHASE_TIMEOUT_SECONDS )); then
      echo "Timed out waiting for $label currentView id=$expected_id members=$expected_members" >&2
      for role in "$@"; do
        echo "--- $role currentView inspection ---" >&2
        java -cp "$APP_JAR:$DIST/lib/*" progressrisk.bftsmart.ViewInspector \
          "$RUNTIME/$role/config/currentView" "$expected_id" "$expected_members" >&2 || true
      done
      return 1
    fi
    sleep 0.25
  done
}

copy_verified_view() {
  local source_role="$1" destination_role="$2" expected_id="$3" expected_members="$4"
  local source="$RUNTIME/$source_role/config/currentView"
  local destination="$RUNTIME/$destination_role/config/currentView"
  view_matches "$source" "$expected_id" "$expected_members" || \
    fail "source view from $source_role is not expected id=$expected_id members=$expected_members"
  rm -f "$destination"
  cp "$source" "$destination"
  view_matches "$destination" "$expected_id" "$expected_members" || \
    fail "copied view into $destination_role failed verification"
}

run_reconfiguration() {
  local phase="$1" logfile="$2"
  shift 2
  set +e
  (
    cd "$RUNTIME/ttp"
    exec timeout "${COMMAND_TIMEOUT_SECONDS}s" ./smartrun.sh bftsmart.reconfiguration.util.DefaultVMServices "$@"
  ) > "$logfile" 2>&1
  local rc=$?
  set -e
  (( rc == 0 )) || {
    tail -n 220 "$logfile" >&2 || true
    fail "$phase reconfiguration command exited with code $rc"
  }
}

run_fresh_client() {
  local role="$1" client_id="$2" expected_first="$3" phase="$4"
  local logfile="$LOGS/${phase}_client.log"
  set +e
  (
    cd "$RUNTIME/$role"
    exec timeout "${COMMAND_TIMEOUT_SECONDS}s" ./smartrun.sh \
      progressrisk.bftsmart.HandoffSequenceClient "$client_id" "$expected_first" 1 "$phase"
  ) > "$logfile" 2>&1
  local rc=$?
  set -e
  (( rc == 0 )) || {
    tail -n 220 "$logfile" >&2 || true
    fail "$phase client exited with code $rc"
  }
  grep -Eq "HANDOFF_CLIENT_REPLY phase=$phase sequence=1 value=$expected_first expected=$expected_first" "$logfile" || \
    fail "$phase client did not log validated reply $expected_first"
}

# Build exactly the BFT-SMaRt v2.0 distribution that A0/A1 use.
DIST="$BFTSMART_HOME/build/install/library"
if (( SKIP_BUILD == 0 )); then
  (
    cd "$BFTSMART_HOME"
    ./gradlew --no-daemon installDist
  )
fi
[[ -x "$DIST/smartrun.sh" ]] || fail 'BFT-SMaRt installDist did not create smartrun.sh'

rm -rf "$LOGS" "$RUNTIME" "$APP_BUILD"
mkdir -p "$LOGS" "$RUNTIME" "$APP_BUILD/classes"

javac -source 8 -target 8 -cp "$DIST/lib/*" -d "$APP_BUILD/classes" \
  "$APP_SOURCE/StatefulCounterServer.java" \
  "$APP_SOURCE/HandoffSequenceClient.java" \
  "$APP_SOURCE/ViewInspector.java"
APP_JAR="$APP_BUILD/progressrisk-handoff-a2.jar"
jar cf "$APP_JAR" -C "$APP_BUILD/classes" .

cat > "$RESULTS_DIR/metadata.txt" <<META
mode=single_real_stateful_4_to_5_to_4_handoff
bftsmart_ref=$(git -C "$BFTSMART_HOME" rev-parse HEAD 2>/dev/null || true)
java=$(java -version 2>&1 | tr '\n' ';')
snapshot_bytes=$SNAPSHOT_BYTES
port_base=$PORT_BASE
checkpoint_period=2
initial_members=0,1,2,3
post_add_members=0,1,2,3,4
final_members=1,2,3,4
META
printf 'event\tepoch_ms\tdetail\n' > "$METRICS"
printf 'A2_HANDOFF_STARTED\n' > "$VERDICT"

# Every process sees the same complete host map, but only the replica process
# associated with an ID binds that ID's unique client/server ports. Starting
# from a fresh copied distribution prevents stale currentView files or leaked
# ports from prior Actions runs from affecting the test.
write_hosts() {
  local hosts="$1"
  cat > "$hosts" <<HOSTS
0 127.0.0.1 $PORT_BASE $((PORT_BASE + 1))
1 127.0.0.1 $((PORT_BASE + 10)) $((PORT_BASE + 11))
2 127.0.0.1 $((PORT_BASE + 20)) $((PORT_BASE + 21))
3 127.0.0.1 $((PORT_BASE + 30)) $((PORT_BASE + 31))
4 127.0.0.1 $((PORT_BASE + 40)) $((PORT_BASE + 41))
HOSTS
}

for role in replica0 replica1 replica2 replica3 replica4 ttp client_add client_remove; do
  mkdir -p "$RUNTIME/$role"
  cp -a "$DIST/." "$RUNTIME/$role/"
  cp "$APP_JAR" "$RUNTIME/$role/lib/"
  rm -f "$RUNTIME/$role/config/currentView"
  write_hosts "$RUNTIME/$role/config/hosts.config"
  sed -i -E 's|^[[:space:]]*system\.totalordermulticast\.checkpoint_period[[:space:]]*=.*$|system.totalordermulticast.checkpoint_period = 2|' \
    "$RUNTIME/$role/config/system.config"
  grep -Eq '^system\.totalordermulticast\.checkpoint_period[[:space:]]*=[[:space:]]*2$' \
    "$RUNTIME/$role/config/system.config" || fail "could not set checkpoint period for $role"
  chmod +x "$RUNTIME/$role/smartrun.sh"
done

# Start the four initial committee members and wait for BFT-SMaRt's official
# readiness marker before issuing any ordered request.
for id in 0 1 2 3; do
  (
    cd "$RUNTIME/replica$id"
    exec ./smartrun.sh progressrisk.bftsmart.StatefulCounterServer "$id" "$SNAPSHOT_BYTES"
  ) > "$LOGS/replica${id}.log" 2>&1 &
  replica_pid[$id]="$!"
  all_pids+=("${replica_pid[$id]}")
done
for id in 0 1 2 3; do
  wait_marker "initial replica $id" 'Ready to process operations' "$LOGS/replica${id}.log" \
    "${replica_pid[$id]}" "$READY_TIMEOUT_SECONDS" || fail "initial replica $id did not become ready"
done
printf 'initial_replicas_ready\t%s\t0,1,2,3\n' "$(now_ms)" >> "$METRICS"

# Warm up the stateful service. A1 already validated the service in isolation;
# this creates the non-empty application state which replica 4 must recover.
set +e
(
  cd "$RUNTIME/client_add"
  exec timeout "${COMMAND_TIMEOUT_SECONDS}s" ./smartrun.sh \
    progressrisk.bftsmart.HandoffSequenceClient 1002 1 3 warmup
) > "$LOGS/warmup_client.log" 2>&1
warmup_rc=$?
set -e
(( warmup_rc == 0 )) || { tail -n 220 "$LOGS/warmup_client.log" >&2 || true; fail "warmup client exited with code $warmup_rc"; }
grep -Eq 'HANDOFF_CLIENT_REPLY phase=warmup sequence=3 value=3 expected=3' "$LOGS/warmup_client.log" || \
  fail 'warmup did not reach counter value 3'
for id in 0 1 2 3; do
  grep -Eq "STATEFUL_SNAPSHOT_WRITTEN id=$id counter=[1-9][0-9]* operations=[1-9][0-9]*" "$LOGS/replica${id}.log" || \
    fail "initial replica $id did not serialize the warmup state"
done
printf 'warmup_complete\t%s\tcounter=3\n' "$(now_ms)" >> "$METRICS"

# Replica 4 is intentionally started before the add command. Because it is not
# in the initial view, official ServiceReplica creates its listener then waits
# for a TTP join message. This proves the join target is live before addServer.
(
  cd "$RUNTIME/replica4"
  exec ./smartrun.sh progressrisk.bftsmart.StatefulCounterServer 4 "$SNAPSHOT_BYTES"
) > "$LOGS/replica4.log" 2>&1 &
replica_pid[4]="$!"
all_pids+=("${replica_pid[4]}")
wait_marker 'joining replica 4' 'Waiting for the TTP' "$LOGS/replica4.log" "${replica_pid[4]}" "$READY_TIMEOUT_SECONDS" || \
  fail 'replica 4 did not bind and wait for the TTP join message'
printf 'replica4_waiting_for_ttp\t%s\tport=%s\n' "$(now_ms)" "$((PORT_BASE + 40))" >> "$METRICS"

add_start="$(now_ms)"
printf 'add_command_start\t%s\tadd replica=4\n' "$add_start" >> "$METRICS"
run_reconfiguration add "$LOGS/ttp_add.log" 4 127.0.0.1 "$((PORT_BASE + 40))" "$((PORT_BASE + 41))"
printf 'add_command_returned\t%s\tadd replica=4\n' "$(now_ms)" >> "$METRICS"

wait_views 'post-add old replicas' 1 '0,1,2,3,4' replica0 replica1 replica2 replica3 || \
  fail 'old replicas did not install view 1 after add'
add_view_ready="$(now_ms)"
printf 'view1_installed\t%s\tall_initial_replicas\n' "$add_view_ready" >> "$METRICS"

wait_views 'post-add joining replica' 1 '0,1,2,3,4' replica4 || fail 'replica 4 did not install view 1'
# Regression guard: sources must expose checkpoint CID 2 and a proof-bearing
# log entry at CID 3. This is the exact state-transfer geometry required for
# the joining replica to install the non-empty application snapshot.
for id in 0 1 2 3; do
  wait_marker "source replica $id state proof" 'Constructing ApplicationState up until CID 3' \
    "$LOGS/replica${id}.log" "${replica_pid[$id]}" "$PHASE_TIMEOUT_SECONDS" || \
    fail "source replica $id did not construct proof-bearing state for CID 3"
  grep -Fq 'CID requested: 3. Last checkpoint: 2. Last CID: 3' "$LOGS/replica${id}.log" || \
    fail "source replica $id has invalid checkpoint/log geometry for CID 3"
done
printf 'state_transfer_sources_ready\t%s\tcheckpoint=2;cid=3\n' "$(now_ms)" >> "$METRICS"
wait_marker 'replica 4 state transfer' 'STATE_TRANSFER_INSTALLED id=4 counter=3 operations=3' \
  "$LOGS/replica4.log" "${replica_pid[4]}" "$PHASE_TIMEOUT_SECONDS" || \
  fail 'replica 4 did not install the transferred non-empty state'
state_ready="$(now_ms)"
printf 'state_transfer_installed\t%s\treplica=4 counter=3\n' "$state_ready" >> "$METRICS"

# New clients must receive the latest currentView after group reconfiguration.
copy_verified_view replica1 client_add 1 '0,1,2,3,4'
run_fresh_client client_add 1003 4 post_add
post_add_reply="$(now_ms)"
printf 'post_add_reply\t%s\tcounter=4\n' "$post_add_reply" >> "$METRICS"
grep -Fq 'STATEFUL_COUNTER_ORDERED id=4 counter=4 operations=4' "$LOGS/replica4.log" || \
  fail 'replica 4 did not execute the first post-add ordered operation'

# The TTP itself also needs the new view before it can submit the removal.
copy_verified_view replica1 ttp 1 '0,1,2,3,4'
remove_start="$(now_ms)"
printf 'remove_command_start\t%s\tremove replica=0\n' "$remove_start" >> "$METRICS"
run_reconfiguration remove "$LOGS/ttp_remove.log" 0
printf 'remove_command_returned\t%s\tremove replica=0\n' "$(now_ms)" >> "$METRICS"

wait_views 'post-remove survivors' 2 '1,2,3,4' replica1 replica2 replica3 replica4 || \
  fail 'survivors did not install final view 2 {1,2,3,4}'
remove_view_ready="$(now_ms)"
printf 'view2_installed\t%s\tsurvivors=1,2,3,4\n' "$remove_view_ready" >> "$METRICS"

copy_verified_view replica1 client_remove 2 '1,2,3,4'
run_fresh_client client_remove 1004 5 post_remove
post_remove_reply="$(now_ms)"
printf 'post_remove_reply\t%s\tcounter=5\n' "$post_remove_reply" >> "$METRICS"
grep -Fq 'STATEFUL_COUNTER_ORDERED id=4 counter=5 operations=5' "$LOGS/replica4.log" || \
  fail 'replica 4 did not execute the final post-remove ordered operation'

{
  printf 'metric\tvalue_ms\n'
  printf 'T_add_view_ms\t%s\n' "$(( add_view_ready - add_start ))"
  printf 'T_state_ready_ms\t%s\n' "$(( state_ready - add_start ))"
  printf 'T_post_add_reply_ms\t%s\n' "$(( post_add_reply - add_start ))"
  printf 'T_remove_view_ms\t%s\n' "$(( remove_view_ready - remove_start ))"
  printf 'T_cycle_ms\t%s\n' "$(( post_remove_reply - add_start ))"
} > "$RESULTS_DIR/summary_metrics.tsv"

printf 'A2_HANDOFF_PASS\nfinal_view=2\nfinal_members=1,2,3,4\nsnapshot_bytes=%s\n' "$SNAPSHOT_BYTES" >> "$VERDICT"
echo 'A2 passed: real stateful 4 -> 5 -> 4 membership handoff completed.'
