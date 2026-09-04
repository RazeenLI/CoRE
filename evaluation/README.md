# Evaluation 使用指南

Evaluation 分为两步：

1. `evaluator.py`：计算每个 case 的指标并生成 CSV。
2. `aggregate_result.py`：汇总不同数据规模或多次实验的 CSV。

## 1. 运行单次 Evaluation

首先修改 `evaluation/evaluator.py` 顶部的三个列表：

```python
DATASETS = ["Chinook", "MONDIAL"]
MODELS = ["standard", "oneshot"]
SIZES = ["small", "medium", "large"]
```

脚本会运行三个列表的全部组合，并自动使用以下路径：

- benchmark：`data/<dataset>/benchmarks/<size>`
- 模型结果：`save/<dataset>/<model>/<size>`
- evaluation CSV：`outputs/<dataset>/<model>/<size>.csv`

`SAMPLE_NUM` 控制读取的 CSV 样本数；当前指标不依赖数据行，可以保持为 `0`。

然后在项目根目录运行：

```bash
conda activate /data1/runzel/TimeSeriesImputation/.conda
python -m evaluation.evaluator
```

例如，以上配置会自动生成：

```text
outputs/Chinook/standard/small.csv
outputs/Chinook/standard/medium.csv
outputs/Chinook/standard/large.csv
```

如果某个 case 缺少 `proposal.json` 或 `database/`，CSV 中会记录：

```text
evaluation_status=missing_result
```

结果存在并成功计算指标时记录：

```text
evaluation_status=evaluated
```

## 2. 汇总 Evaluation 结果

确认 `evaluation/aggregate_result.py` 顶部的 `RESULT_FILES` 指向需要汇总的 CSV：

```python
RESULT_FILES = [
    "outputs/Chinook/standard/small.csv",
    "outputs/Chinook/standard/medium.csv",
    "outputs/Chinook/standard/large.csv",
]
```

运行：

```bash
python -m evaluation.aggregate_result
```

汇总结果保存在：

```text
outputs/summary/
```

如果只完成了某一种数据规模，只在 `RESULT_FILES` 中保留已经存在的 CSV，避免 `FileNotFoundError`。

## 3. 多次实验

同一数据规模的多次结果可以使用编号：

```text
outputs/Chinook/standard/medium_1.csv
outputs/Chinook/standard/medium_2.csv
```

将它们都加入 `RESULT_FILES` 后，aggregate 会计算多次实验的均值和标准差。

## 4. Pending model-sensitivity experiments

### TODO: Core LLM sensitivity

Evaluate whether the framework gain over OneShot depends on the current Qwen3.5-9B backbone. On one fixed, pre-declared subset, run both Standard and OneShot with Qwen3.5-9B and Qwen3-8B. Use MONDIAL and TPC-DS and sample five cases from each dataset--size--operation cell (90 distinct cases; 360 method/backbone runs). Keep prompts, MPNet retrieval, top-k, sampled rows, decoding, retry limits, proposal construction, and case IDs fixed. Report Decision Macro-F1, Column F1, Proposal F1, Checked-valid, final-schema exact match, latency, tokens, and LLM calls. This is a backbone-sensitivity experiment, not a claim of cross-family generalization. Save all four subset runs under distinct output labels (`standard_qwen3.5_9b_subset`, `oneshot_qwen3.5_9b_subset`, `standard_qwen3_8b_subset`, and `oneshot_qwen3_8b_subset`) while retaining `standard` and `oneshot` as pipeline names; this preserves the full existing outputs and makes the token comparison paired.

### TODO: Validator LLM sensitivity

Replace only the current Validator with a stronger, larger LLM while retaining Qwen3.5-9B for the Profiler and Evolutor. First replay Validator models on the same saved first-round Evolutor proposals and before/after previews, holding the prompt, decoding, and deterministic gate fixed. Report detection precision/recall, false acceptance/rejection, route agreement, latency, and tokens. Then run the full revision loop only for the retained larger Validator and report correction, harm, repair success, retries, retry exhaustion, final proposal quality, and added cost. Load the larger Validator sequentially or in a separate replay process if two resident models exceed GPU memory; do not infer Validator-model effects from runs in which the Profiler or Evolutor model also changes.

### TODO: Matching-adapter sensitivity

The primary matching baselines use one shared deterministic correspondence-to-proposal adapter. Add `Magneto-LLM` first: feed Magneto's retrieved/reranked correspondences to the unmodified Standard Evolutor prompt, without Standard's semantic profiles, Candidate Selector, or Validator. If useful, apply the identical LLM adapter to other matching methods. Add successful variants directly to the main result table rather than creating a separate paper subsection. Report native correspondence quality and adapted end-to-end quality so that matcher errors can be separated from adapter-induced errors.
