# Utilities

The current utility package contains:

- `io.py`: JSON/CSV loading and saving, RDB loading, table loading, and terminal
  messages.
- `structure.py`: conversion and filtering helpers for the compact structures
  passed between pipeline stages.

Dataset-specific SQL and SQLite preparation tools live under `data/` rather
than in the online pipeline utility package.
