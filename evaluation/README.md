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

## 4. Model-sensitivity experiment status

### Core LLM sensitivity: completed run with two failed outputs

The fixed subset contains five cases from every dataset--size--operation cell in MONDIAL and TPC-DS (90 distinct cases). All scheduled jobs have terminated. Qwen3.5-9B produced all 180 method/case outputs; Qwen3-8B produced 178/180, with no evaluable output for Standard TPC-DS small `case_0023` or OneShot TPC-DS medium `case_0032`. The paper therefore reports coverage and computes quality metrics over available outputs; a strictly paired comparison must use the common successful-case subset or count the failed outputs explicitly.

| Dataset | Backbone | Method | Coverage | Decision Macro-F1 | Column F1 | Proposal F1 | Checked-valid | Schema Exact | Calls | Input tokens | Output tokens | Latency (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MONDIAL | Qwen3.5-9B | Standard | 1.000 | 0.956 | 0.756 | 0.716 | 0.978 | 0.578 | 3.00 | 12,134 | 801 | 90.4 |
| MONDIAL | Qwen3.5-9B | OneShot | 1.000 | 0.782 | 0.741 | 0.677 | 0.867 | 0.578 | 1.00 | 9,497 | 339 | 34.3 |
| MONDIAL | Qwen3-8B | Standard | 1.000 | 0.446 | 0.431 | 0.456 | 0.467 | 0.400 | 4.58 | 20,371 | 1,114 | 95.7 |
| MONDIAL | Qwen3-8B | OneShot | 1.000 | 0.335 | 0.476 | 0.494 | 0.511 | 0.422 | 1.00 | 8,235 | 360 | 29.4 |
| TPC-DS | Qwen3.5-9B | Standard | 1.000 | 0.816 | 0.507 | 0.443 | 0.822 | 0.467 | 3.47 | 41,805 | 2,030 | 197.3 |
| TPC-DS | Qwen3.5-9B | OneShot | 1.000 | 0.649 | 0.500 | 0.420 | 0.711 | 0.489 | 1.00 | 33,123 | 755 | 82.0 |
| TPC-DS | Qwen3-8B | Standard | 0.978 | 0.214 | 0.218 | 0.274 | 0.205 | 0.364 | 4.43 | 50,093 | 2,046 | 167.4 |
| TPC-DS | Qwen3-8B | OneShot | 0.978 | 0.217 | 0.357 | 0.341 | 0.227 | 0.432 | 1.00 | 28,723 | 770 | 64.3 |

These results show sensitivity to backbone capability. Standard improves decision Macro-F1 over OneShot with Qwen3.5-9B on both datasets and with Qwen3-8B on MONDIAL, but the Qwen3-8B advantage does not extend consistently to placement, proposal, validity, or final-schema exact match. A non-Qwen backbone remains pending if cross-family evidence is required.

### TODO: Validator LLM sensitivity

Replace only the current Validator with a stronger, larger LLM while retaining Qwen3.5-9B for the Profiler and Evolutor. First replay Validator models on the same saved first-round Evolutor proposals and before/after previews, holding the prompt, decoding, and deterministic gate fixed. Report detection precision/recall, false acceptance/rejection, route agreement, latency, and tokens. Then run the full revision loop only for the retained larger Validator and report correction, harm, repair success, retries, retry exhaustion, final proposal quality, and added cost. Load the larger Validator sequentially or in a separate replay process if two resident models exceed GPU memory; do not infer Validator-model effects from runs in which the Profiler or Evolutor model also changes.

### Matching-adapter sensitivity: Magneto-LLM completed

The primary matching baselines use one shared deterministic correspondence-to-proposal adapter. `Magneto-LLM` instead feeds Magneto's retrieved/reranked correspondences to the unmodified Standard Evolutor prompt, without Standard's semantic profiles, Candidate Selector, or Validator. This isolates whether the weak end-to-end results of the matching baselines are caused only by the deterministic adapter.

All scheduled Magneto-LLM jobs have terminated, producing 1,072/1,100 evaluable outputs: Chinook 149/150, MONDIAL 245/250, TPC-DS 179/200, and Spider 499/500. Missing outputs remain part of result coverage rather than being silently discarded.

| Dataset | Coverage | Decision Acc. | Decision Macro-F1 | Column F1 | Proposal F1 | Checked-valid | Schema Exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chinook | 0.993 | 0.758 | 0.752 | 0.699 | 0.606 | 0.819 | 0.497 |
| MONDIAL | 0.980 | 0.849 | 0.840 | 0.694 | 0.639 | 0.980 | 0.522 |
| TPC-DS | 0.895 | 0.749 | 0.743 | 0.637 | 0.556 | 0.911 | 0.469 |
| Spider | 0.998 | 0.822 | 0.812 | 0.691 | 0.632 | 0.820 | 0.467 |

Magneto-LLM substantially improves over the deterministic Magneto adaptation on decision and proposal quality, but remains below Standard on decision Macro-F1 and Proposal F1 across all four benchmarks. Native correspondence quality and adapter-induced error attribution remain separate fairness analyses; the completed end-to-end run does not by itself provide those metrics.
