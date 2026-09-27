# Contributing

Thank you for your interest in CoRE. Before opening a pull request, please:

1. Create a Python 3.11 environment and install the development dependencies:

   ```bash
   python -m pip install -e ".[all]"
   ```

2. Run the unit tests:

   ```bash
   python -m pytest
   ```

3. Keep generated run outputs under `save/`, logs under `logs/`, and aggregate
   evaluation outputs under `outputs/`. Do not commit model checkpoints,
   credentials, or newly generated raw datasets.

4. Document new models in `main.py`, `README.md`, and the relevant page under
   `docs/`. Add or update tests when behavior changes.

For dataset contributions, record the source, retrieval date, license, and all
transformations in `DATA_LICENSES.md` and `data/README.md`.
