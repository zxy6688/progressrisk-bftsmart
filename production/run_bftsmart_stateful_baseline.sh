#!/usr/bin/env bash
# A1 gate: the project stateful service on the *already-passing* official
# BFT-SMaRt v2.0 four-replica startup skeleton. There are no membership
# operations here. A2 handoff is locked until this gate passes.
set -Eeuo pipefail

: "${BFTSMART_HOME:?Set BFTSMART_HOME to a BFT-SMaRt v2.0 checkout}"
: "${RESULTS_DIR:=./bftsmart_stateful_baseline}"
: "${SNAPSHOT_BYTES:=1048576}"
: "${READY_TIMEOUT_SECONDS:=150}"
: "${CLIENT_TIMEOUT_SECONDS:=75}"
: "${STATEFUL_OPERATIONS:=3}"

for integer_name in SNAPSHOT_BYTES READY_TIMEOUT_SECONDS CLIENT_TIMEOUT_SECONDS STATEFUL_OPERATIONS; do
  value="${!integer_name}"
  case "$value" in
    ''|*[!0-9]*) echo "$integer_name must be a nonnegative integer" >&2; exit 2 ;;
  esac
done
(( SNAPSHOT_BYTES >= 0 )) || { echo 'SNAPSHOT_BYTES must be >= 0' >&2; exit 2; }
(( READY_TIMEOUT_SECONDS >= 1 && CLIENT_TIMEOUT_SECONDS >= 1 && STATEFUL_OPERATIONS >= 1 )) || {
  echo 'timeouts and STATEFUL_OPERATIONS must be >= 1' >&2; exit 2;
}

[[ -x "$BFTSMART_HOME/gradlew" ]] || {
  echo "BFTSMART_HOME is not a BFT-SMaRt source checkout: $BFTSMART_HOME" >&2
  exit 2
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SOURCE="$ROOT_DIR/production/java"
[[ -f "$APP_SOURCE/StatefulCounterServer.java" && -f "$APP_SOURCE/StatefulCounterClient.java" ]] || {
  echo "missing A1 Java sources under $APP_SOURCE" >&2
  exit 2
}

mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"
LOGS="$RESULTS_DIR/logs"
RUNTIME="$RESULTS_DIR/runtime"
APP_BUILD="$RESULTS_DIR/app_build"
VERDICT="$RESULTS_DIR/verdict.txt"

pids=()
cleanup() {
  local pid
  for pid in "${pids[@]:-}"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "${pids[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

fail() {
  echo "FAIL: $*" >&2
  printf 'STATEFUL_BASELINE_FAIL\nreason=%s\n' "$*" > "$VERDICT"
  exit 1
}

wait_for_marker() {
  local id="$1" marker="$2" logfile="$3" pid="$4" start="$SECONDS"
  while ! grep -Fq "$marker" "$logfile" 2>/dev/null; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Replica $id exited before marker: $marker" >&2
      tail -n 180 "$logfile" >&2 || true
      return 1
    fi
    if (( SECONDS - start >= READY_TIMEOUT_SECONDS )); then
      echo "Timed out waiting for replica $id marker: $marker" >&2
      tail -n 180 "$logfile" >&2 || true
      return 1
    fi
    sleep 0.25
  done
}

# Compile against the exact pinned BFT-SMaRt distribution using the same Java 8
# runtime as the passing official A0 workflow. The app jar is added to lib/ so
# official smartrun.sh retains control of JVM security/logging/classpath flags.
(
  cd "$BFTSMART_HOME"
  ./gradlew --no-daemon installDist
)
DIST="$BFTSMART_HOME/build/install/library"
[[ -x "$DIST/smartrun.sh" ]] || fail "BFT-SMaRt installDist did not create smartrun.sh"

rm -rf "$LOGS" "$RUNTIME" "$APP_BUILD"
mkdir -p "$LOGS" "$RUNTIME" "$APP_BUILD/classes"

javac -source 8 -target 8 -cp "$DIST/lib/*" -d "$APP_BUILD/classes" \
  "$APP_SOURCE/StatefulCounterServer.java" "$APP_SOURCE/StatefulCounterClient.java"
jar cf "$APP_BUILD/progressrisk-stateful-a1.jar" -C "$APP_BUILD/classes" .

cat > "$RESULTS_DIR/metadata.txt" <<META
mode=stateful_four_replica_baseline
bftsmart_ref=$(git -C "$BFTSMART_HOME" rev-parse HEAD 2>/dev/null || true)
java=$(java -version 2>&1 | tr '\n' ';')
snapshot_bytes=$SNAPSHOT_BYTES
stateful_operations=$STATEFUL_OPERATIONS
ready_timeout_seconds=$READY_TIMEOUT_SECONDS
client_timeout_seconds=$CLIENT_TIMEOUT_SECONDS
META

# Same independent local-directory layout that passed A0. We change exactly one
# state-transfer-relevant parameter: checkpoint period 1 forces a snapshot after
# live ordered operations so A1 validates mutated-state serialization.
for role in replica0 replica1 replica2 replica3 client; do
  mkdir -p "$RUNTIME/$role"
  cp -a "$DIST/." "$RUNTIME/$role/"
  cp "$APP_BUILD/progressrisk-stateful-a1.jar" "$RUNTIME/$role/lib/"
  rm -f "$RUNTIME/$role/config/currentView"
  sed -i -E 's|^[[:space:]]*system\.totalordermulticast\.checkpoint_period[[:space:]]*=.*$|system.totalordermulticast.checkpoint_period = 1|' \
    "$RUNTIME/$role/config/system.config"
  grep -Eq '^system\.totalordermulticast\.checkpoint_period[[:space:]]*=[[:space:]]*1$' \
    "$RUNTIME/$role/config/system.config" || fail "could not set checkpoint period for $role"
  chmod +x "$RUNTIME/$role/smartrun.sh"
done

for id in 0 1 2 3; do
  (
    cd "$RUNTIME/replica$id"
    exec ./smartrun.sh progressrisk.bftsmart.StatefulCounterServer "$id" "$SNAPSHOT_BYTES"
  ) > "$LOGS/replica${id}.log" 2>&1 &
  pids+=("$!")
done

for id in 0 1 2 3; do
  wait_for_marker "$id" 'Ready to process operations' "$LOGS/replica${id}.log" "${pids[$id]}" || \
    fail "replica $id did not become ready"
done
printf 'ALL_FOUR_STATEFUL_REPLICAS_READY\n' > "$VERDICT"

set +e
(
  cd "$RUNTIME/client"
  timeout "${CLIENT_TIMEOUT_SECONDS}s" ./smartrun.sh \
    progressrisk.bftsmart.StatefulCounterClient 1002 1 "$STATEFUL_OPERATIONS"
) > "$LOGS/client.log" 2>&1
client_rc=$?
set -e
(( client_rc == 0 )) || fail "stateful client exited with code $client_rc"

reply_count="$(grep -Ec 'STATEFUL_CLIENT_REPLY sequence=[0-9]+ value=[0-9]+ expected=[0-9]+' "$LOGS/client.log" || true)"
[[ "$reply_count" -eq "$STATEFUL_OPERATIONS" ]] || \
  fail "expected $STATEFUL_OPERATIONS validated stateful replies, found $reply_count"

for id in 0 1 2 3; do
  grep -Fq "STATEFUL_COUNTER_ORDERED id=$id" "$LOGS/replica${id}.log" || \
    fail "replica $id did not execute an ordered stateful operation"
  grep -Eq "STATEFUL_SNAPSHOT_WRITTEN id=$id counter=[1-9][0-9]* operations=[1-9][0-9]*" "$LOGS/replica${id}.log" || \
    fail "replica $id did not serialize a snapshot after state mutation"
done

printf 'STATEFUL_BASELINE_PASS\nvalidated_stateful_replies=%s\nsnapshot_bytes=%s\n' \
  "$reply_count" "$SNAPSHOT_BYTES" >> "$VERDICT"
echo "A1 stateful baseline passed with $reply_count validated replies and $SNAPSHOT_BYTES-byte snapshots."
