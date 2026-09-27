# Development

## Tests

Install the test dependencies and run:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

The GitHub Actions workflow runs the same unit tests on Python 3.11.

## Adding a pipeline

1. Implement a callable `run_pipeline` entry point.
2. Register its module in `main.py`.
3. Add configuration defaults under `configs/`.
4. Add unit tests that do not require downloading a full LLM checkpoint.
5. Update the model table in the root README and the appropriate documentation.

## Generated files

Keep ordinary run outputs under `save/`, evaluator CSV files under `outputs/`,
logs under `logs/`, and figures under `visualization/figures/`. These paths are
ignored except for explicitly curated artifact directories.

Do not commit secrets, model checkpoints, generated TPC-DS rows, or downloaded
third-party archives. When adding a dataset, update `DATA_LICENSES.md` with its
source and redistribution terms.

## Research status documents

`evaluation/EVALUATION_METRICS.md` tracks metric implementation and future
analysis work. It is a development roadmap rather than end-user usage
documentation; the stable evaluation procedure is documented in
`docs/evaluation.md`.
