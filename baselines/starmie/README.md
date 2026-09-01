# Starmie baseline

This directory contains only an AIRDB adapter. The official Starmie source is
not copied because its repository does not declare a software license.

## 1. Train one external checkpoint

Clone the official repository outside this project and prepare an external
VizNet CSV directory. The compatibility trainer uses the official Starmie
dataset, augmentation, serialization, and model modules with the current AIRDB
PyTorch environment; it does not require Apex or MLflow:

```bash
git clone https://github.com/megagonlabs/starmie.git /data1/runzel/starmie
bash baselines/starmie/download_viznet.sh /data1/runzel/starmie_data
```

The downloader uses the VizNet archive published by the SATO/Starmie authors.
The trainer discovers CSV files recursively, so the extracted fold hierarchy
does not need to be flattened manually.

```bash
CUDA_VISIBLE_DEVICES=0 python -m baselines.starmie.train \
  --upstream-path /absolute/path/to/starmie \
  --data-path /data1/runzel/starmie_data/viznet_tables \
  --output /absolute/path/to/starmie_viznet.pt \
  --batch-size 64 \
  --learning-rate 5e-5 \
  --epochs 3 \
  --max-length 128 \
  --size 10000 \
  --projector 768 \
  --augment-op drop_col \
  --sample-method head \
  --table-order column \
  --seed 0
```

Use the resulting checkpoint unchanged for every AIRDB benchmark. No Chinook,
MONDIAL, TPC-DS, or reference-state table may enter pretraining.

## 2. Run the adapter

```bash
export STARMIE_ROOT=/absolute/path/to/starmie
export STARMIE_CHECKPOINT=/absolute/path/to/starmie_viznet.pt
MODEL=starmie DATASET=Chinook DATASIZE=small ./run_cases.sh
```

Each case includes checkpoint loading, table encoding, bipartite matching, and
proposal construction in end-to-end latency. One-time VizNet pretraining is
reported separately. The adapter follows the official contextual encoder and
matching procedure but adds the shared AIRDB evolution-rule conversion.

Official repository: https://github.com/megagonlabs/starmie
