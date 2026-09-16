#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Core-LLM sensitivity experiment for Standard only.
#
# It uses the same deterministic, operation-stratified subset for every model:
#   2 datasets x 3 sizes x 3 operations x 5 cases = 90 cases/model.
#
# Qwen3-8B and Qwen3.5-9B already have subset outputs, so the default list
# contains only the five additional models. Override CORE_MODELS to select a
# smoke-test-free execution plan, for example:
#   CORE_MODELS="qwen3.5_2b llama3.1_8b" ./run_core_llm.sh

PYTHON_BIN="${PYTHON_BIN:-python}"
GPU_IDS="${GPU_IDS:-0,1,2,3}"
DATASETS="${DATASETS:-MONDIAL TPCDS}"
SIZES="${SIZES:-small medium large}"
CASES_PER_OPERATION="${CASES_PER_OPERATION:-5}"
CORE_MODELS="${CORE_MODELS:-qwen3.5_2b qwen3.5_27b llama3.1_8b deepseek_coder_v2_lite gpt_oss_20b}"
DRY_RUN="${DRY_RUN:-false}"
failed_cells=0

config_for_model() {
    case "$1" in
        qwen3_8b) echo "configs/qwen3_8B.yaml" ;;
        qwen3.5_9b) echo "configs/qwen3.5_9B.yaml" ;;
        qwen3.5_2b) echo "configs/core_llm/qwen3.5_2B.yaml" ;;
        qwen3.5_27b) echo "configs/core_llm/qwen3.5_27B.yaml" ;;
        llama3.1_8b) echo "configs/core_llm/llama3.1_8B.yaml" ;;
        deepseek_coder_v2_lite) echo "configs/core_llm/deepseek_coder_v2_lite.yaml" ;;
        gpt_oss_20b) echo "configs/core_llm/gpt_oss_20B.yaml" ;;
        validator_qwen3.5_27b) echo "configs/validator_qwen3.5_27B.yaml" ;;
        *)
            echo "[Core LLM] Unknown model label: $1" >&2
            return 1
            ;;
    esac
}

select_cases() {
    "$PYTHON_BIN" - "$1" "$2" "$CASES_PER_OPERATION" <<'PY'
import glob
import json
import sys

dataset, size, count_text = sys.argv[1:4]
count = int(count_text)
selected = []

for operation in ("insert_table", "extend_table", "create_table"):
    candidates = []
    pattern = f"data/{dataset}/benchmarks/{size}/case_*/expected/proposal.json"
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as file:
            proposal = json.load(file)
        if proposal["decision"] == operation:
            candidates.append(path.split("/")[-3])
    if len(candidates) < count:
        raise SystemExit(
            f"{dataset}/{size}/{operation} has only {len(candidates)} cases; "
            f"requested {count}."
        )
    selected.extend(candidates[:count])

print(" ".join(selected))
PY
}

for model_label in $CORE_MODELS; do
    agent_config="$(config_for_model "$model_label")" || exit 1
    if [[ ! -f "$agent_config" ]]; then
        echo "[Core LLM] Missing config: $agent_config" >&2
        exit 1
    fi

    output_label="standard_${model_label}_subset"
    for dataset in $DATASETS; do
        for size in $SIZES; do
            cases="$(select_cases "$dataset" "$size")" || exit 1
            echo "[Core LLM] $model_label Standard $dataset/$size"

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "[Core LLM] dry-run config=$agent_config output=$output_label cases=$cases"
                continue
            fi

            # Word splitting is intentional: run_cases.sh takes case IDs as
            # separate positional arguments.
            # shellcheck disable=SC2086
            if ! GPU_IDS="$GPU_IDS" \
                MODEL=standard \
                OUTPUT_MODEL="$output_label" \
                AGENT_CONFIG="$agent_config" \
                DATASET="$dataset" \
                DATASIZE="$size" \
                FAIL_BATCH_ON_CASE_ERROR=true \
                "$SCRIPT_DIR/run_cases.sh" $cases; then
                failed_cells=$((failed_cells + 1))
                echo "[Core LLM] $model_label $dataset/$size reported failures."
            fi
        done
    done
done

if (( failed_cells > 0 )); then
    echo "[Core LLM] $failed_cells cell(s) reported failed cases."
    if [[ "${FAIL_BATCH_ON_CASE_ERROR:-false}" == "true" ]]; then
        exit 1
    fi
fi
