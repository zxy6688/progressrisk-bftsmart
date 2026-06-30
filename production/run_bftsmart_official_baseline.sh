#!/usr/bin/env bash
# Strict gate for the unmodified BFT-SMaRt v2.0 Counter demonstration.
# It intentionally does not load ProgressRisk classes or run membership changes.
set -Eeuo pipefail

: "${BFTSMART_HOME:?Set BFTSMART_HOME to a BFT-SMaRt v2.0 checkout}"
: "${RESULTS_DIR:=./bftsmart_official_baseline}"
: "${READY_TIMEOUT_SECONDS:=120}"
: "${CLIENT_TIMEOUT_SECONDS:=60}"
: "${COUNTER_OPERATIONS:=3}"

case "$COUNTER_OPERATIONS" in
  ''|*[!0-9]*) echo "COUNTER_OPERATIONS must be a positive integer" >&2; exit 2 ;;
esac
(( COUNTER_OPERATIONS >= 1 )) || { echo "COUNTER_OPERATIONS must be >= 1" >&2; exit 2; }

mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"
LOGS="$RESULTS_DIR/logs"
RUNTIME="$RESULTS_DIR/runtime"

[[ -x "$BFTSMART_HOME/gradlew" ]] || {
  echo "BFTSMART_HOME is not a BFT-SMaRt source checkout: $BFTSMART_HOME" >&2
  exit 2
}

pids=()
cleanup() {
  local pid
  for pid in "${pids[@]:-}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  for pid in "${pids[@]:-}"; do
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

fail() {
  echo "FAIL: $*" >&2
  printf 'OFFICIAL_COUNTER_BASELINE_FAIL\nreason=%s\n' "$*" > "$RESULTS_DIR/verdict.txt"
  exit 1
}

wait_for_ready() {
  local id="$1" logfile="$2" pid="$3" start="$SECONDS"
  while ! grep -Fq 'Ready to process operations' "$logfile" 2>/dev/null; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Replica $id exited before readiness." >&2
      tail -n 120 "$logfile" >&2 || true
      return 1
    fi
    if (( SECONDS - start >= READY_TIMEOUT_SECONDS )); then
      echo "Timed out waiting for replica $id readiness." >&2
      tail -n 120 "$logfile" >&2 || true
      return 1
    fi
    sleep 0.25
  done
}

# Build the exact upstream source pinned by the workflow.
(
  cd "$BFTSMART_HOME"
  ./gradlew --no-daemon installDist
)

DIST="$BFTSMART_HOME/build/install/library"
[[ -x "$DIST/smartrun.sh" ]] || fail "BFT-SMaRt installDist did not create $DIST/smartrun.sh"
[[ -f "$DIST/config/hosts.config" ]] || fail "missing official config/hosts.config"
[[ -f "$DIST/config/system.config" ]] || fail "missing official config/system.config"

rm -rf "$RUNTIME" "$LOGS"
mkdir -p "$RUNTIME" "$LOGS"

cat > "$RESULTS_DIR/metadata.txt" <<META
mode=official_counter_baseline
bftsmart_ref=$(git -C "$BFTSMART_HOME" rev-parse HEAD 2>/dev/null || true)
java=$(java -version 2>&1 | tr '\n' ';')
ready_timeout_seconds=$READY_TIMEOUT_SECONDS
client_timeout_seconds=$CLIENT_TIMEOUT_SECONDS
counter_operations=$COUNTER_OPERATIONS
META

# Upstream explicitly instructs users to copy the distribution into separate
# local folders. Each process starts with the untouched official configuration.
for role in replica0 replica1 replica2 replica3 client; do
  mkdir -p "$RUNTIME/$role"
  cp -a "$DIST/." "$RUNTIME/$role/"
  rm -f "$RUNTIME/$role/config/currentView"
  chmod +x "$RUNTIME/$role/smartrun.sh"
done

for id in 0 1 2 3; do
  (
    cd "$RUNTIME/replica$id"
    exec ./smartrun.sh bftsmart.demo.counter.CounterServer "$id"
  ) > "$LOGS/replica${id}.log" 2>&1 &
  pids+=("$!")
done

for id in 0 1 2 3; do
  wait_for_ready "$id" "$LOGS/replica${id}.log" "${pids[$id]}" || fail "replica $id did not become ready"
done
printf 'ALL_FOUR_REPLICAS_READY\n' > "$RESULTS_DIR/verdict.txt"

# The third argument is intentional: it bounds this gate to exactly three
# ordered Counter operations instead of the upstream client's 1000-op default.
set +e
(
  cd "$RUNTIME/client"
  timeout "${CLIENT_TIMEOUT_SECONDS}s" ./smartrun.sh bftsmart.demo.counter.CounterClient 1001 1 "$COUNTER_OPERATIONS"
) > "$LOGS/client.log" 2>&1
client_rc=$?
set -e
(( client_rc == 0 )) || fail "official CounterClient exited with code $client_rc"

reply_count="$(grep -Ec 'returned value:[[:space:]]*[0-9]+' "$LOGS/client.log" || true)"
[[ "$reply_count" -eq "$COUNTER_OPERATIONS" ]] || fail "expected $COUNTER_OPERATIONS completed Counter replies, found $reply_count"

for id in 0 1 2 3; do
  grep -Fq 'Counter was incremented' "$LOGS/replica${id}.log" || fail "replica $id did not execute the Counter operation"
done

printf 'OFFICIAL_COUNTER_BASELINE_PASS\ncompleted_counter_replies=%s\n' "$reply_count" >> "$RESULTS_DIR/verdict.txt"
echo "Official BFT-SMaRt Counter baseline passed with $reply_count ordered replies."
