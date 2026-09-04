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

Evaluate whether the complete framework depends on the current Qwen3.5-9B backbone. At minimum, compare Qwen3.5-9B with Qwen3-8B while keeping prompts, MPNet retrieval, top-k, sampled rows, decoding, retry limits, proposal construction, and benchmark cases fixed. Replace the shared LLM used by the Profiler, Evolutor, and Validator together. Report Decision Macro-F1, Column F1, Proposal F1, Checked-valid, final-schema exact match, latency, and LLM calls. Use a pre-declared subset stratified by dataset, operation, and context size if a full 1,100-case rerun is too expensive. With only Qwen-family models, describe this as backbone sensitivity rather than cross-family generalization.

### TODO: Validator LLM sensitivity

First replay different Validator models on the same saved first-round Evolutor proposals and before/after previews, holding the prompt, decoding, and deterministic route controls fixed. Report detection precision/recall, false acceptance/rejection, route agreement, latency, and tokens. Then run the full revision loop only for retained Validator configurations and report correction, harm, repair success, retries, retry exhaustion, final proposal quality, and added cost. Do not infer Validator-model effects from runs in which the Profiler or Evolutor model also changes.

### TODO: Matching-adapter sensitivity

The primary matching baselines use one shared deterministic correspondence-to-proposal adapter. If an LLM adapter is evaluated, feed it only the matcher output, incoming table, and associated schema/constraint context; do not provide Standard's semantic profiles or unrestricted database context. Add successful variants directly to the main result table rather than creating a separate paper subsection. Report native correspondence quality and adapted end-to-end quality so that matcher errors can be separated from adapter-induced errors.
