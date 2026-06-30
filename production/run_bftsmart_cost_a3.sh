#!/usr/bin/env bash
# A3: final single-committee membership-handoff cost study.
# One state-size job executes PAIRS adjacent matched control/handoff pairs.
# Every PASS row must be backed by a concrete A1/A2 verdict and metrics file.
# Artifacts retain compact, audit-ready evidence instead of bulky runtime copies.
set -Eeuo pipefail

: "${BFTSMART_HOME:?Set BFTSMART_HOME}"
: "${RESULTS_DIR:=./bftsmart_final_cost}"
: "${SNAPSHOT_BYTES:?Set SNAPSHOT_BYTES}"
: "${STATE_LABEL:?Set STATE_LABEL}"
: "${PAIRS:=20}"
: "${READY_TIMEOUT_SECONDS:=150}"
: "${PHASE_TIMEOUT_SECONDS:=180}"
: "${COMMAND_TIMEOUT_SECONDS:=75}"
: "${SKIP_BUILD:=0}"

for integer_name in SNAPSHOT_BYTES PAIRS READY_TIMEOUT_SECONDS PHASE_TIMEOUT_SECONDS COMMAND_TIMEOUT_SECONDS SKIP_BUILD; do
  value="${!integer_name}"
  case "$value" in ''|*[!0-9]*) echo "$integer_name must be a nonnegative integer" >&2; exit 2 ;; esac
done
(( PAIRS >= 1 )) || { echo 'PAIRS must be >= 1' >&2; exit 2; }
(( SKIP_BUILD == 0 || SKIP_BUILD == 1 )) || { echo 'SKIP_BUILD must be 0 or 1' >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A1="$ROOT_DIR/production/run_bftsmart_stateful_baseline.sh"
A2="$ROOT_DIR/production/run_bftsmart_handoff_a2.sh"
[[ -x "$BFTSMART_HOME/gradlew" ]] || { echo "not a BFT-SMaRt checkout: $BFTSMART_HOME" >&2; exit 2; }
[[ -f "$A1" && -f "$A2" ]] || { echo 'A3 requires bundled A1 and A2 runners' >&2; exit 2; }

mkdir -p "$RESULTS_DIR"
RESULTS_DIR="$(cd "$RESULTS_DIR" && pwd)"
RAW="$RESULTS_DIR/a3_raw_trials.tsv"
META="$RESULTS_DIR/metadata.txt"

metric_value() {
  local path="$1" name="$2"
  awk -F $'\t' -v n="$name" '$1 == n { print $2; exit }' "$path" 2>/dev/null || true
}

compact_trial() {
  local run_dir="$1" treatment="$2"
  {
    echo "treatment=$treatment"
    [[ -f "$run_dir/verdict.txt" ]] && { echo '--- verdict ---'; cat "$run_dir/verdict.txt"; }
    [[ -f "$run_dir/summary_metrics.tsv" ]] && { echo '--- metrics ---'; cat "$run_dir/summary_metrics.tsv"; }
    [[ -f "$run_dir/metadata.txt" ]] && { echo '--- metadata ---'; cat "$run_dir/metadata.txt"; }
    echo '--- protocol evidence ---'
    grep -R -E 'STATE_TRANSFER_INSTALLED|state_transfer_sources_ready|STATEFUL_COUNTER_ORDERED id=4 counter=[45]|A2_HANDOFF_(PASS|FAIL)|STATEFUL_BASELINE_(PASS|FAIL)' "$run_dir/logs" 2>/dev/null || true
    echo '--- log tails ---'
    for log in "$run_dir"/logs/*.log; do
      [[ -f "$log" ]] || continue
      echo "### $(basename "$log")"
      tail -n 35 "$log" || true
    done
  } > "$run_dir/compact_evidence.txt"
  # Runtime directories contain copied distributions and snapshot files; raw
  # metrics/evidence above are sufficient for the final report and keep the
  # Actions artifact reasonably sized.
  rm -rf "$run_dir/runtime" "$run_dir/app_build" "$run_dir/logs"
}

if (( SKIP_BUILD == 0 )); then
  (
    cd "$BFTSMART_HOME"
    ./gradlew --no-daemon installDist
  )
fi
[[ -x "$BFTSMART_HOME/build/install/library/smartrun.sh" ]] || {
  echo 'BFT-SMaRt installDist did not create smartrun.sh' >&2; exit 1;
}

cat > "$META" <<META
experiment=single_committee_membership_handoff_cost
state_label=$STATE_LABEL
snapshot_payload_bytes=$SNAPSHOT_BYTES
pairs=$PAIRS
checkpoint_period=2
bftsmart_ref=$(git -C "$BFTSMART_HOME" rev-parse HEAD 2>/dev/null || true)
java=$(java -version 2>&1 | tr '\n' ';')
control=A1 four-member stateful no-reconfiguration baseline, checkpoint period 2
handoff=A2 real stateful 0,1,2,3 -> 0,1,2,3,4 -> 1,2,3,4, checkpoint period 2
META
printf 'state_label\tsnapshot_payload_bytes\tpair\ttreatment\torder\tstatus\tport_base\tT_control_3ops_ms\tT_add_view_ms\tT_state_ready_ms\tT_post_add_reply_ms\tT_remove_view_ms\tT_cycle_ms\tresult_dir\n' > "$RAW"

failures=0
for pair in $(seq 1 "$PAIRS"); do
  if (( pair % 2 == 1 )); then modes=(control handoff); else modes=(handoff control); fi
  order="${modes[0]}-then-${modes[1]}"
  for mode in "${modes[@]}"; do
    if [[ "$mode" == control ]]; then
      port_base=$((30000 + (pair - 1) * 200))
      run_dir="$RESULTS_DIR/pair_$(printf '%02d' "$pair")/control"
      set +e
      BFTSMART_HOME="$BFTSMART_HOME" RESULTS_DIR="$run_dir" SNAPSHOT_BYTES="$SNAPSHOT_BYTES" \
      READY_TIMEOUT_SECONDS="$READY_TIMEOUT_SECONDS" CLIENT_TIMEOUT_SECONDS="$COMMAND_TIMEOUT_SECONDS" \
      PORT_BASE="$port_base" SKIP_BUILD=1 bash "$A1"
      rc=$?
      set -e
      t_control="$(metric_value "$run_dir/summary_metrics.tsv" T_control_3ops_ms)"
      if (( rc == 0 )) && grep -Fq 'STATEFUL_BASELINE_PASS' "$run_dir/verdict.txt" 2>/dev/null && [[ -n "$t_control" ]]; then
        status=PASS
      else
        status=FAIL; failures=$((failures + 1)); t_control=NA
      fi
      compact_trial "$run_dir" control
      printf '%s\t%s\t%s\tcontrol\t%s\t%s\t%s\t%s\tNA\tNA\tNA\tNA\tNA\t%s\n' \
        "$STATE_LABEL" "$SNAPSHOT_BYTES" "$pair" "$order" "$status" "$port_base" "$t_control" \
        "${run_dir#$RESULTS_DIR/}" >> "$RAW"
    else
      port_base=$((30000 + (pair - 1) * 200 + 80))
      run_dir="$RESULTS_DIR/pair_$(printf '%02d' "$pair")/handoff"
      set +e
      BFTSMART_HOME="$BFTSMART_HOME" RESULTS_DIR="$run_dir" SNAPSHOT_BYTES="$SNAPSHOT_BYTES" \
      READY_TIMEOUT_SECONDS="$READY_TIMEOUT_SECONDS" PHASE_TIMEOUT_SECONDS="$PHASE_TIMEOUT_SECONDS" \
      COMMAND_TIMEOUT_SECONDS="$COMMAND_TIMEOUT_SECONDS" PORT_BASE="$port_base" SKIP_BUILD=1 bash "$A2"
      rc=$?
      set -e
      add_view="$(metric_value "$run_dir/summary_metrics.tsv" T_add_view_ms)"
      state_ready="$(metric_value "$run_dir/summary_metrics.tsv" T_state_ready_ms)"
      post_add="$(metric_value "$run_dir/summary_metrics.tsv" T_post_add_reply_ms)"
      remove_view="$(metric_value "$run_dir/summary_metrics.tsv" T_remove_view_ms)"
      cycle="$(metric_value "$run_dir/summary_metrics.tsv" T_cycle_ms)"
      if (( rc == 0 )) && grep -Fq 'A2_HANDOFF_PASS' "$run_dir/verdict.txt" 2>/dev/null && \
         [[ -n "$add_view" && -n "$state_ready" && -n "$post_add" && -n "$remove_view" && -n "$cycle" ]]; then
        status=PASS
      else
        status=FAIL; failures=$((failures + 1)); add_view=NA; state_ready=NA; post_add=NA; remove_view=NA; cycle=NA
      fi
      compact_trial "$run_dir" handoff
      printf '%s\t%s\t%s\thandoff\t%s\t%s\t%s\tNA\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$STATE_LABEL" "$SNAPSHOT_BYTES" "$pair" "$order" "$status" "$port_base" \
        "$add_view" "$state_ready" "$post_add" "$remove_view" "$cycle" \
        "${run_dir#$RESULTS_DIR/}" >> "$RAW"
    fi
    sleep 1
  done
done

if (( failures > 0 )); then
  printf 'A3_STATE_JOB_FAIL\nstate_label=%s\nfailures=%s\n' "$STATE_LABEL" "$failures" > "$RESULTS_DIR/verdict.txt"
  echo "A3 $STATE_LABEL complete with $failures failed trial(s); compact evidence retained." >&2
  exit 1
fi
printf 'A3_STATE_JOB_PASS\nstate_label=%s\npairs=%s\n' "$STATE_LABEL" "$PAIRS" > "$RESULTS_DIR/verdict.txt"
echo "A3 $STATE_LABEL passed: $PAIRS matched control/handoff pairs completed."
