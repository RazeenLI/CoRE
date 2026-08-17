# AIRDB Maintenance

AI-assisted relational database maintenance for integrating one incoming table into an existing RDB.

当前提供两种运行模式：

- `standard`：Profiler → Matcher → Evolutor（需要时）→ Proposal → Preview → Validator → Decision → Apply。
- `oneshot`：One-shot Evolutor → Proposal → Preview → Decision → Apply。

两种模式使用相同的输入配置和输出结构，可以使用同一套 evaluation。

## 1. 环境准备

```bash
cd /data1/runzel/AIRDB_maintenance
conda activate /data1/runzel/TimeSeriesImputation/.conda
python --version
```

当前运行环境为 Python 3.11。首次使用 Hugging Face 模型时：

```bash
hf auth login
hf auth whoami
```

默认 Agent 配置为：

```text
configs/qwen3.5_9B.yaml
```

每个 case 的 `config.yaml` 必须包含一个 existing RDB 和且仅包含一个 incoming table。

## 2. 运行单个 Case

### Standard

```bash
CUDA_VISIBLE_DEVICES=0,1,2,4,5 \
python -u main.py \
  --model standard \
  --output save/Chinook/standard/medium/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/medium/case_0001/config.yaml
```

### One-shot baseline

```bash
CUDA_VISIBLE_DEVICES=0,1,3,4 \
python -u main.py \
  --model oneshot \
  --output save/Chinook/oneshot/medium/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/medium/case_0001/config.yaml
```

## 3. 批量运行

`run_cases.sh` 默认运行 `Chinook/standard/medium`。

运行一个数据规模下的全部 case：

```bash
GPU_IDS=0,1,3,4 \
MODEL=standard \
DATASET=Chinook \
DATASIZE=medium \
./run_cases.sh
```

运行 One-shot baseline：

```bash
GPU_IDS=1,2,4,5 \
MODEL=oneshot \
DATASET=Chinook \
DATASIZE=medium \
./run_cases.sh
```

只运行指定 case：

```bash
MODEL=standard DATASIZE=medium \
./run_cases.sh case_0001 case_0003 case_0010
```

后台运行：

```bash
GPU_IDS=0,1,2,4 MODEL=magneto DATASIZE=large \
nohup ./run_cases.sh > logs/nohup_magneto_large.log 2>&1 &
```

可选环境变量：

- `MODEL`：`standard` 或 `oneshot`。
- `DATASET`：数据集名称，默认 `Chinook`。
- `DATASIZE`：`small`、`medium` 或 `large`。
- `GPU_IDS`：CUDA GPU 编号。
- `MAX_ATTEMPTS`：运行异常时的最大尝试次数，默认 `3`。
- `RETRY_INTERVAL_SECONDS`：重试等待时间，默认 `60` 秒。

## 4. 输出结构

Standard 和 One-shot 使用相同格式：

```text
save/Chinook/<model>/<size>/<case>/
├── task_state.json
├── proposal.json
└── database/
    ├── schema.json
    ├── profiles.json
    ├── constraints.json
    └── tables/
        └── <table_name>.csv
```

- `task_state.json`：Task 状态、各 step 结果、routing 和 trace。
- `proposal.json`：最终结构化集成 proposal。
- `database/`：应用 proposal 后的 RDB。

`task_state.json` 中：

- `status: "succeeded"`：Task 完成。
- `status: "failed"`：Task 实际运行过，但流程结果失败，文件仍应保留用于检查。

Python 异常、模型加载失败或 CUDA OOM 属于运行异常，由 `run_cases.sh` 根据进程退出码重试。日志保存在 `logs/`。

## 5. Evaluation

Standard 和 One-shot 都通过各 case 的 `proposal.json` 与 `database/` 计算指标。

```bash
python -m evaluation.evaluator
python -m evaluation.aggregate_result
```

运行前需要在对应文件中设置输入和输出路径。详细说明见 [Evaluation 使用指南](evaluation/README.md)。

## 6. 主要入口

- `main.py`：统一命令行入口。
- `model/pipeline.py`：Standard pipeline。
- `baselines/oneshot/pipeline.py`：One-shot baseline pipeline。
- `run_cases.sh`：批量运行和异常重试。
- `evaluation/evaluator.py`：case-level evaluation。
- `evaluation/aggregate_result.py`：结果汇总。
