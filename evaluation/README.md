# Evaluation 使用指南

Evaluation 分为两步：

1. `evaluator.py`：计算每个 case 的指标并生成 CSV。
2. `aggregate_result.py`：汇总不同数据规模或多次实验的 CSV。

## 1. 运行单次 Evaluation

首先修改 `evaluation/evaluator.py` 底部 `main()` 中的三个路径：

```python
evaluate_benchmark(
    benchmark_dir="data/Chinook/benchmarks/medium",
    result_dir="save/Chinook/standard/medium",
    output_csv_path="outputs/Chinook/standard/medium.csv",
    sample_num=0,
)
```

路径含义：

- `benchmark_dir`：benchmark case 的根目录。
- `result_dir`：模型运行结果目录，其中每个 case 应包含 `proposal.json` 和 `database/`。
- `output_csv_path`：case-level evaluation CSV 的保存位置。
- `sample_num`：读取的 CSV 样本数；当前指标不依赖数据行，可以使用 `0`。

然后在项目根目录运行：

```bash
conda activate /data1/runzel/TimeSeriesImputation/.conda
python -m evaluation.evaluator
```

分别评估 small、medium 和 large 时，修改上述三个路径后各运行一次，建议输出为：

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
