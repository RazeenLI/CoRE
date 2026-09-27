# Installation

## Requirements

- Python 3.11 or later. The code uses standard-library features introduced in
  Python 3.11.
- A CUDA-capable GPU is recommended for local LLM pipelines. CPU execution is
  possible for preprocessing, evaluation, and several rule-based components.
- Sufficient storage for the committed benchmark cases and generated outputs.

## Core environment

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The authoritative dependency metadata is in `pyproject.toml`. A convenience
`requirements.txt` is also provided for tools that expect that filename:

```bash
python -m pip install -r requirements.txt
```

## Optional dependencies

Install the Valentine-based JL and COMA baselines:

```bash
python -m pip install -e ".[traditional]"
```

Install plotting dependencies:

```bash
python -m pip install -e ".[visualization]"
```

Install test dependencies:

```bash
python -m pip install -e ".[test]"
```

Install all optional groups:

```bash
python -m pip install -e ".[all]"
```

## Model access

The default configuration uses `Qwen/Qwen3.5-9B` and
`sentence-transformers/all-mpnet-base-v2`. Hugging Face downloads are cached by
the local environment. Authenticate before using a gated model:

```bash
hf auth login
hf auth whoami
```

Set `CUDA_VISIBLE_DEVICES` or the batch runner's `GPU_IDS` variable to control
which GPUs are visible. Do not assume that device numbers from another machine
are valid locally.

## Verify the installation

Run the unit tests without downloading an LLM checkpoint:

```bash
python -m pytest
```

Some tests import PyTorch, but the test suite does not run the full benchmark
or load the default Qwen model.
