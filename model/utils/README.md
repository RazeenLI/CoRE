# `utils/`

The `utils/` directory contains general-purpose helper functions.

## `io.py`

Handles file reading and writing.

Examples:

```
load_json
save_json
load_csv
save_csv
list_files
```

## `sql_utils.py`

Contains utilities for benchmark preprocessing from SQL or SQLite sources.

This module is not part of the online schema-maintenance pipeline. It is used to convert raw database sources into the project’s standard benchmark format.

Examples:

```
extract schema from SQLite
export SQLite tables to CSV
execute a SQLite SQL script into a temporary database
```

## `table_profile_utils.py`

Computes non-LLM table and column profiles.

Examples:

```
infer column type
compute null rate
compute distinct ratio
detect email values
detect date values
detect numeric columns
estimate candidate key score
```

## `json_utils.py`

Handles JSON parsing and repair, especially for LLM outputs.

Examples:

```
extract JSON from model output
validate JSON structure
repair minor formatting issues
```