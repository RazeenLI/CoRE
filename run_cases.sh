#!/usr/bin/env bash

set -uo pipefail

# ============================================================
# Configuration
# ============================================================

PYTHON_BIN="${PYTHON_BIN:-python}"
MODEL="${MODEL:-standard}" # standard grain_profiler constraint_filter llm_matcher no_profiler no_selector oneshot magneto jl coma
DATASET="${DATASET:-Chinook}"
DATASIZE="${DATASIZE:-medium}"

MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

MAIN_SCRIPT="main.py"
DATA_ROOT="data/$DATASET/benchmarks/$DATASIZE"
OUTPUT_ROOT="save/$DATASET/$MODEL/$DATASIZE"
AGENT_CONFIG="configs/qwen3.5_9B.yaml"
LOG_ROOT="logs"


# 每轮失败任务重新执行前的等待时间，单位：秒
RETRY_INTERVAL_SECONDS="${RETRY_INTERVAL_SECONDS:-60}"

GPU_IDS="${GPU_IDS:-0,1,3,4}"
export CUDA_VISIBLE_DEVICES="$GPU_IDS"


# ============================================================
# Locate project root
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/main.py" ]]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../main.py" ]]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    echo "[Error] Cannot locate project root containing main.py."
    exit 1
fi

cd "$PROJECT_ROOT"


# ============================================================
# Validation
# ============================================================

if [[ ! -f "$MAIN_SCRIPT" ]]; then
    echo "[Error] Main script not found: $MAIN_SCRIPT"
    exit 1
fi

if [[ ! -d "$DATA_ROOT" ]]; then
    echo "[Error] Data directory not found: $DATA_ROOT"
    exit 1
fi

if [[ ! -f "$AGENT_CONFIG" ]]; then
    echo "[Error] Agent config not found: $AGENT_CONFIG"
    exit 1
fi

mkdir -p "$OUTPUT_ROOT"
mkdir -p "$LOG_ROOT"


# ============================================================
# Logging
# ============================================================

RUN_ID="$(date '+%Y%m%d_%H%M%S')"
SUMMARY_LOG="$LOG_ROOT/batch_${RUN_ID}.log"

log_message() {
    local message="$1"
    local timestamp

    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    printf '[%s] %s\n' "$timestamp" "$message" | tee -a "$SUMMARY_LOG"
}

# ============================================================
# Discover/select cases
#
# Usage:
#   ./run_cases.sh
#       Run all cases.
#
#   ./run_cases.sh case_0001 case_0003 case_0010
#       Run only the specified cases.
# ============================================================

shopt -s nullglob

declare -a ALL_CASES=()
declare -a MISSING_CASE_DIRS=()
declare -a MISSING_CONFIG_CASES=()
declare -A SEEN_CASES=()


# ------------------------------------------------------------
# Case list provided: only run requested cases
# ------------------------------------------------------------

if (( $# > 0 )); then
    for case_name in "$@"; do
        # Ignore duplicated case names
        if [[ -n "${SEEN_CASES[$case_name]+x}" ]]; then
            continue
        fi

        SEEN_CASES["$case_name"]=1

        case_dir="$DATA_ROOT/$case_name"
        data_config="$case_dir/config.yaml"

        if [[ ! -d "$case_dir" ]]; then
            MISSING_CASE_DIRS+=("$case_name")
            continue
        fi

        if [[ ! -f "$data_config" ]]; then
            MISSING_CONFIG_CASES+=("$case_name")
            continue
        fi

        ALL_CASES+=("$case_name")
    done


# ------------------------------------------------------------
# No case list provided: discover and run all cases
# ------------------------------------------------------------

else
    for case_dir in "$DATA_ROOT"/case*; do
        [[ -d "$case_dir" ]] || continue

        case_name="$(basename "$case_dir")"
        data_config="$case_dir/config.yaml"

        if [[ ! -f "$data_config" ]]; then
            MISSING_CONFIG_CASES+=("$case_name")
            continue
        fi

        ALL_CASES+=("$case_name")
    done
fi


# ------------------------------------------------------------
# Validate selected/discovered cases
# ------------------------------------------------------------

if (( ${#MISSING_CASE_DIRS[@]} > 0 )); then
    echo "[Error] The following requested case directories do not exist:"

    for case_name in "${MISSING_CASE_DIRS[@]}"; do
        echo "  - $DATA_ROOT/$case_name"
    done

    exit 1
fi

if (( ${#MISSING_CONFIG_CASES[@]} > 0 )); then
    echo "[Error] The following cases do not contain config.yaml:"

    for case_name in "${MISSING_CONFIG_CASES[@]}"; do
        echo "  - $DATA_ROOT/$case_name/config.yaml"
    done

    exit 1
fi

if (( ${#ALL_CASES[@]} == 0 )); then
    if (( $# > 0 )); then
        echo "[Error] No valid requested cases were found."
    else
        echo "[Error] No case directories found under: $DATA_ROOT"
    fi

    exit 1
fi


# ============================================================
# Run and retry failed cases
# ============================================================

declare -A ATTEMPTS=()
declare -A FINAL_FAILURES=()
declare -a PENDING_CASES=("${ALL_CASES[@]}")

round=1

log_message "Batch started."
log_message "Cases found: ${#ALL_CASES[@]}"
log_message "Cases: ${ALL_CASES[*]}"

while (( ${#PENDING_CASES[@]} > 0 )); do
    declare -a FAILED_CASES=()

    log_message "Starting round $round with ${#PENDING_CASES[@]} case(s)."

    for case_name in "${PENDING_CASES[@]}"; do
        data_config="$DATA_ROOT/$case_name/config.yaml"
        output_path="$OUTPUT_ROOT/$case_name"
        case_log_dir="$LOG_ROOT/$case_name"

        mkdir -p "$output_path"
        mkdir -p "$case_log_dir"

        previous_attempt="${ATTEMPTS[$case_name]:-0}"
        attempt=$((previous_attempt + 1))
        ATTEMPTS["$case_name"]="$attempt"

        attempt_number="$(printf '%03d' "$attempt")"
        attempt_timestamp="$(date '+%Y%m%d_%H%M%S')"
        log_file="$case_log_dir/attempt_${attempt_number}_${attempt_timestamp}.log"

        log_message "Running $case_name, attempt $attempt."

        {
            echo "============================================================"
            echo "Case:         $case_name"
            echo "Model:        $MODEL"
            echo "Attempt:      $attempt"
            echo "Data config:  $data_config"
            echo "Agent config: $AGENT_CONFIG"
            echo "Output:       $output_path"
            echo "Started:      $(date '+%Y-%m-%d %H:%M:%S')"
            echo "============================================================"
        } | tee "$log_file"

        "$PYTHON_BIN" -u "$MAIN_SCRIPT" \
            --model "$MODEL" \
            --output "$output_path" \
            --data-config "$data_config" \
            --agent-config "$AGENT_CONFIG" \
            2>&1 | tee -a "$log_file"

        exit_code=${PIPESTATUS[0]}

        {
            echo "============================================================"
            echo "Finished:  $(date '+%Y-%m-%d %H:%M:%S')"
            echo "Exit code: $exit_code"
            echo "============================================================"
        } | tee -a "$log_file"

        if (( exit_code == 0 )); then
            log_message "$case_name succeeded on attempt $attempt."
        else
            if (( attempt < MAX_ATTEMPTS )); then
                FAILED_CASES+=("$case_name")
                log_message "$case_name failed on attempt $attempt with exit code $exit_code; it will be retried."
            else
                FINAL_FAILURES["$case_name"]="$exit_code"
                log_message "$case_name permanently failed after $attempt attempts with exit code $exit_code."
            fi
        fi
    done

    if (( ${#FAILED_CASES[@]} == 0 )); then
        PENDING_CASES=()
        break
    fi

    PENDING_CASES=("${FAILED_CASES[@]}")

    log_message "Round $round completed. Failed cases: ${PENDING_CASES[*]}"
    log_message "Retrying failed cases after ${RETRY_INTERVAL_SECONDS} seconds."

    sleep "$RETRY_INTERVAL_SECONDS"
    round=$((round + 1))
done


# ============================================================
# Final summary
# ============================================================

if (( ${#FINAL_FAILURES[@]} > 0 )); then
    log_message "Batch completed with ${#FINAL_FAILURES[@]} permanently failed case(s)."

    for case_name in "${!FINAL_FAILURES[@]}"; do
        log_message "$case_name failed after ${ATTEMPTS[$case_name]} attempt(s), final exit code: ${FINAL_FAILURES[$case_name]}."
    done

    log_message "Summary log: $SUMMARY_LOG"
    exit 1
fi

log_message "All cases completed successfully."

for case_name in "${ALL_CASES[@]}"; do
    log_message "$case_name completed after ${ATTEMPTS[$case_name]} attempt(s)."
done

log_message "Summary log: $SUMMARY_LOG"
