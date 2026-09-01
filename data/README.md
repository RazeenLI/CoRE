# Dataset preparation

This directory turns a complete relational database dump into benchmark cases for schema evolution:

```text
raw PostgreSQL dump
  -> parsed relational database
  -> semantic table profiles
  -> small / medium / large benchmark cases
```

The complete parsed database is treated as ground truth. `form_benchmark.py` hides tables, columns, or rows to construct an incomplete `existing` database and supplies the hidden information as an `incoming` table. The corresponding complete state is stored in `expected`.

## Case Size

Each case should be a local RDB maintenance scenario, rather than a full database-level task.

| Subset    | Small case (3–5 tables) | Medium case (6–9 tables) | Large case (10–15 tables) | Total case count |
| --------- | ----------------------- | ------------------------ | ------------------------- | ---------------- |
| Chinook   | 50                      | 60                       | 40                        | 150        |
| TPC-DS    | 60                      | 80                       | 60                        | 200        |
| MONDIAL   | 70                      | 100                      | 80                        | 250        |
| Spider    | 200                     | 175                      | 125                       | 500        |
| **Total** | **370**                 | **640**                  | **530**                   | **1540**   |

The counts above are the target benchmark composition. They should be reported as final dataset statistics only after all cases have been generated and validated.

### Paper-facing benchmark contribution

A central contribution of this work is a benchmark for relational schema-maintenance decisions. Rather than evaluating on a single database, the benchmark draws complete relational schemas from Chinook, TPC-DS, MONDIAL, and Spider, covering conventional business databases, analytical warehouses, densely connected geographical data, and heterogeneous cross-domain schemas. Each complete database is treated as ground truth and systematically transformed into paired `existing`, `incoming`, and `expected` states. The cases exercise three maintenance decisions—extending an existing table, creating a new table, and inserting rows into an existing table—under small, medium, and large relational contexts. This construction provides controlled ground-truth actions while varying schema scale, topology, naming overlap, and domain.

Suggested contribution bullet for the Introduction (replace the current target with final validated numbers):

> We construct a multi-source benchmark for relational schema maintenance, comprising paired existing-database, incoming-table, and ground-truth target states derived from four structurally and semantically diverse database sources. The benchmark systematically covers table extension, table creation, and row insertion across small, medium, and large schema contexts, enabling controlled evaluation of both maintenance decisions and the resulting relational structures.

Do not claim that this is the *first* benchmark for the task without a dedicated related-work review. Once generation is complete, strengthen the bullet with the validated numbers of databases, cases, tables, columns, foreign keys, decision classes, and size levels.



## File structure

```text
data/
├── README.md
├── parse_sql.py                 # SQL dump -> schema, constraints, and table CSVs
├── prepare_tpcds.py             # TPC-DS .dat -> common parsed table CSVs
├── profile_parsed_tables.py     # add semantic profiles for parsed tables
├── visualize_rdb.py             # generate ER and referential-dependency reports
├── form_benchmark.py            # parsed database -> benchmark cases
├── Chinook/
│   ├── raw/Chinook_PostgreSql.sql
│   ├── parsed/
│   │   ├── schema.json
│   │   ├── constraints.json
│   │   ├── profiles.json
│   │   ├── tables/<table>.csv
│   │   └── viz/                 # optional generated documentation
│   ├── configs/{small,medium,large}.yaml
│   └── benchmarks/{small,medium,large}/
│       ├── benchmark_config.yaml
│       └── case_XXXX/
│           ├── config.yaml
│           ├── existing/
│           │   ├── schema.json, constraints.json, profiles.json
│           │   └── tables/<table>.csv
│           ├── incoming/
│           │   ├── schema.json, profile.json
│           │   └── table.csv
│           └── expected/
│               ├── schema.json, constraints.json, profiles.json
│               ├── proposal.json
│               └── tables/<table>.csv
├── TPCDS/
│   ├── <download-id>-TPC-DS-Tool.zip
│   ├── raw/
│   │   ├── DSGen-software-code-4.0.0/
│   │   │   ├── tools/tpcds.sql       # 24 business tables + dbgen_version
│   │   │   ├── tools/tpcds_ri.sql    # primary/foreign-key relationships
│   │   │   ├── tools/tpcds_source.sql
│   │   │   └── tools/dsdgen          # locally compiled data generator
│   │   └── sf1/<table>.dat            # generated SF=1 data; local intermediate
│   ├── parsed/
│   │   ├── schema.json, constraints.json, profiles.json
│   │   ├── import_summary.json
│   │   └── tables/<table>.csv
│   ├── configs/{small,medium,large}.yaml
│   └── benchmarks/{small,medium,large}/
└── MONDIAL/
    ├── raw/
    │   ├── mondial-schema.psql       # official PostgreSQL DDL
    │   ├── mondial-inputs.psql       # official PostgreSQL rows
    │   ├── mondial-foreign-keys.sql  # locally transcribed relationships
    │   └── mondial-schema.sql        # original user-prepared combined copy
    └── parsed/
        ├── schema.json, constraints.json, profiles.json
        ├── tables/<table>.csv
        └── viz/
```

The main intermediate files are:

- `schema.json`: tables, columns, normalized data types, and column order.
- `constraints.json`: primary keys, foreign keys, and unique constraints.
- `tables/<table>.csv`: one CSV per table, produced from rows in the SQL dump.
- `profiles.json`: semantic descriptions and aliases used by benchmark perturbations.
- `proposal.json`: the expected schema-evolution decision for one case.

## Raw datasets

### Dataset size overview

`Table count` means the number of base tables in one source relational schema. For Spider, which is a collection of independent databases rather than one RDB, the meaningful unit is the per-database table count; its exact aggregate will be computed from `tables.json` during import.

| Dataset | Source structure | Table count | Count status |
| --- | --- | ---: | --- |
| Chinook | One relational database | 11 | Verified from `Chinook/parsed/schema.json` |
| TPC-DS | One generated relational database | 24 | Verified SF=1 import: 7 fact tables + 17 dimension tables |
| MONDIAL | One relational database | 47 | Verified from `MONDIAL/parsed/schema.json` |
| Spider | 200 independent databases | Varies by database | Exact total pending import from `tables.json` |

The table counts above describe the original complete schemas, not the 3–5, 6–9, or 10–15 table contexts sampled into individual benchmark cases.

### Chinook

[Chinook](https://github.com/lerocha/chinook-database) is a sample digital-media-store database available for several database engines. This repository uses its PostgreSQL dump. Chinook has already been parsed, profiled, and used to generate the committed small, medium, and large benchmark sets.

### TPC-DS

[TPC-DS](https://www.tpc.org/tpcds/) models a retail decision-support system. Its schema contains 24 tables: 7 fact tables and 17 dimension tables. Unlike TPC-H's 8-table schema, TPC-DS can support the shared benchmark case sizes of 3–5, 6–9, and 10–15 tables without redefining the large category.

The official TPC-DS Tools v4.0.0 archive was downloaded from the [TPC specification page](https://www.tpc.org/tpc_documents_current_versions/current_specifications5.asp) and unpacked under `data/TPCDS/raw/`. It contains:

- `tools/tpcds.sql`: ANSI SQL definitions for the 24 business tables plus the auxiliary `dbgen_version` table.
- `tools/tpcds_ri.sql`: 109 `ALTER TABLE ... FOREIGN KEY` statements; the file also relies on primary keys declared by `tpcds.sql`.
- `tools/tpcds_source.sql`: 9 source/staging tables for data-maintenance workloads, excluded from this dataset.
- `tools/dsdgen`: the source and locally compiled executable that generates pipe-delimited `.dat` files.

TPC-DS differs from Chinook and MONDIAL because its official SQL files define the
schema and constraints but do not contain the benchmark rows as `INSERT`
statements. The rows must first be generated by `dsdgen` as pipe-delimited `.dat`
files and then converted to the repository's common per-table CSV format.

The current SQL parser successfully reads the two relevant official SQL files without a compatibility patch:

```bash
python data/parse_sql.py \
  --input \
    data/TPCDS/raw/DSGen-software-code-4.0.0/tools/tpcds.sql \
    data/TPCDS/raw/DSGen-software-code-4.0.0/tools/tpcds_ri.sql \
  --database-name TPCDS \
  --output data/TPCDS/parsed
```

This preliminary parse produces 25 tables, 24 primary-key constraints spanning 32 key columns, and 109 foreign keys. `dbgen_version` has no primary key and is removed during final conversion, leaving the intended 24 business tables, each with a primary key.

On modern GCC, compile only the required data generator with `-fcommon`:

```bash
cd data/TPCDS/raw/DSGen-software-code-4.0.0/tools
make clean
make CC='gcc -fcommon' dsdgen
./dsdgen -release
```

The full `make` target also tries to build `dsqgen` and requires `yacc`; query generation is not needed for this dataset-construction task.

Generate the reproducible SF=1 source rows from the generator's `tools/`
directory, because it resolves distribution files relative to that directory:

```bash
mkdir -p ../../sf1
./dsdgen -SCALE 1 -DIR ../../sf1 -FORCE Y
cd ../../../../..
```

SF=1 produces 25 `.dat` files (24 business tables plus `dbgen_version`) and
occupies approximately 1.2 GB. Convert the business tables after the SQL parse:

```bash
python data/prepare_tpcds.py \
  --raw-dir data/TPCDS/raw/sf1 \
  --parsed data/TPCDS/parsed
```

`prepare_tpcds.py` removes `dbgen_version`, checks every row against the DDL
column count, converts the trailing-pipe `.dat` records to CSV without loading a
whole table into memory, and writes `import_summary.json`.

### TPC-DS import and profile result

The current verified conversion result is:

| Measure | Result |
| --- | ---: |
| Scale factor | 1 |
| Business tables in `schema.json` | 24 |
| Table CSV files | 24 |
| Total data rows | 19,557,375 |
| Tables with primary keys | 24 |
| Primary-key columns | 32 |
| Foreign keys | 109 |

The existing-RDB profiles are generated with `Qwen/Qwen3-8B`, consistently
with Chinook and MONDIAL. Runtime agents use `Qwen/Qwen3.5-9B`; keeping the
offline profiler and runtime agents on different backbones demonstrates that
the two components are model-decoupled. Use the repository's main experiment
environment:

```bash
conda activate /data1/runzel/TimeSeriesImputation/.conda
CUDA_VISIBLE_DEVICES=0,1 \
python data/profile_parsed_tables.py \
  --parsed data/TPCDS/parsed \
  --output data/TPCDS/parsed/profiles.json \
  --model-name Qwen/Qwen3-8B \
  --device-map auto \
  --sample-num 5
```

The current `profiles.json` is the LLM-generated Qwen3-8B version and covers all
24 business tables. A previously generated 60-case small directory was built
before this final profile was available and is therefore a draft; regenerate it
before reporting benchmark statistics. Medium and large generation has not yet
been completed.

The SF=1 `.dat` files and full parsed CSVs are reproducible, large intermediate
artifacts and normally should not be uploaded to GitHub. The compact final
`benchmarks/`, configs, schema, constraints, profiles, summary, preparation code,
and documentation should remain versioned, consistent with Chinook and MONDIAL.

### MONDIAL

[MONDIAL](https://www.dbis.informatik.uni-goettingen.de/Mondial/#SQL) is a geographical database containing countries, cities, organizations, mountains, rivers, and related entities. Its official PostgreSQL distribution provides separate [schema](https://www.dbis.informatik.uni-goettingen.de/Mondial/mondial-schema.psql) and [input](https://www.dbis.informatik.uni-goettingen.de/Mondial/mondial-inputs.psql) scripts.

The official download does **not** include a separate foreign-key SQL file, and `mondial-schema.psql` itself does not declare SQL `FOREIGN KEY` constraints. The website's referential dependency diagram documents the intended relationships, but it is not an executable constraint file. Therefore, foreign keys must be transcribed into a local SQL/JSON artifact or inferred before relationship-aware benchmark generation.

### MONDIAL adaptations made in this repository

The raw source cannot be fed into the original parser unchanged, so the following operations are explicit and reproducible:

1. Preserve the official PostgreSQL schema and inputs as separate raw files. This also avoids encoding damage introduced by copying or incorrectly decoding the download.
2. Extend `parse_sql.py` to accept multiple `--input` files in order. DDL is parsed before the inputs and local relationship declarations.
3. Extend `parse_sql.py` to accept the official `INSERT INTO table VALUES (...)` form. When the column list is absent, values are mapped using the table's DDL column order. A row with the wrong number of values now raises an error instead of being silently truncated.
4. Clear the generated `parsed/tables/` directory on every parse, preventing stale CSV files from surviving a rebuild.
5. Transcribe the official [referential dependency diagram](https://www.dbis.informatik.uni-goettingen.de/Mondial/mondial-abh.pdf) into `mondial-foreign-keys.sql`. This local file is provenance-tracked input, not an official MONDIAL download.
6. Do not encode `Politics.WasDependent` as a hard foreign key. Although the official diagram marks a dependency, the column contains historical entities such as former empires and countries, plus mixed names/codes, so it does not satisfy referential integrity against either `Country.Name` or `Country.Code`.
7. Generate deterministic profiles first with `--no-llm`; these are structural profile skeletons and can later be replaced with LLM-enriched semantic profiles.

The local relationship file contains 72 executable foreign-key declarations. Treat this number as a documented interpretation of the official dependency diagram, rather than a claim that the upstream PostgreSQL distribution ships 72 constraints.

### MONDIAL import result

The initial import was rebuilt from the separately downloaded official PostgreSQL files, not from the user-prepared combined copy. The combined copy is retained for provenance, but is not used because its text contains mojibake (for example, corrupted accented place names).

The verified deterministic import produces:

| Measure | Result |
| --- | ---: |
| Tables in `schema.json` | 47 |
| Table CSV files | 47 |
| Total data rows | 56,702 |
| Tables with primary keys | 45 |
| Locally transcribed foreign keys | 72 |
| Non-null foreign-key violations | 0 |
| Structural table profiles | 47 |

Validation treats a composite foreign key containing any `NULL` component as non-comparable, matching SQL's default `MATCH SIMPLE` behavior. For every remaining foreign-key tuple, the referenced tuple was found in the target table. Unicode was spot-checked after parsing (for example, France's province is preserved as `Île-de-France`).

These counts describe the version downloaded from the official site on 2026-08-22 and should be reported with that retrieval date if used in a paper. MONDIAL is published under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); the official site also provides its recommended academic citation.

## Build a dataset from raw SQL

Run all commands from the repository root. Use Python 3.10 or newer. `form_benchmark.py` requires PyYAML, and LLM profiling requires the model dependencies used by the rest of this project.

### 1. Parse the PostgreSQL dump

For Chinook:

```bash
python data/parse_sql.py \
  --input data/Chinook/raw/Chinook_PostgreSql.sql \
  --output data/Chinook/parsed
```

For MONDIAL, pass the three inputs in dependency order:

```bash
python data/parse_sql.py \
  --input \
    data/MONDIAL/raw/mondial-schema.psql \
    data/MONDIAL/raw/mondial-inputs.psql \
    data/MONDIAL/raw/mondial-foreign-keys.sql \
  --database-name MONDIAL \
  --output data/MONDIAL/parsed
```

The parser handles PostgreSQL `CREATE TABLE`, `ALTER TABLE`, and `INSERT INTO ... VALUES ...` statements, with or without an explicit insert column list. It writes `schema.json`, `constraints.json`, and a CSV for every table that has inserted rows.

After parsing, check the reported `table_count` and `row_count`. Also inspect `constraints.json`; a zero foreign-key count usually means the dump's constraint syntax needs to be adapted before continuing.

### 2. Profile every parsed table

The benchmark generator specifically reads `<parsed>/profiles.json`, so pass that filename explicitly.

With an LLM:

```bash
CUDA_VISIBLE_DEVICES=1,2 \
python data/profile_parsed_tables.py \
  --parsed data/Chinook/parsed \
  --output data/Chinook/parsed/profiles.json \
  --model-name Qwen/Qwen3-8B \
  --device-map auto \
  --sample-num 5
```

For a deterministic skeleton without LLM-generated semantics:

```bash
python data/profile_parsed_tables.py \
  --parsed data/Chinook/parsed \
  --output data/Chinook/parsed/profiles.json \
  --sample-num 5 \
  --no-llm
```

Replace `Chinook` with `MONDIAL` after its parsing step succeeds. For TPC-DS,
use the dataset-specific Qwen3-8B command documented in the TPC-DS section
above. LLM profiles are recommended when `perturbation.use_profile_aliases` is
enabled, because generated aliases are used to rename incoming tables and
columns.

The reproducible structural-profile command used for the initial MONDIAL import is:

```bash
python3.10 data/profile_parsed_tables.py \
  --parsed data/MONDIAL/parsed \
  --output data/MONDIAL/parsed/profiles.json \
  --sample-num 5 \
  --no-llm
```

`--no-llm` no longer imports PyTorch/Transformers; those heavyweight dependencies are needed only when `--model-name` is used.

### 3. Optionally inspect the parsed database

```bash
python data/visualize_rdb.py data/Chinook/parsed
python data/visualize_rdb.py data/MONDIAL/parsed
python data/visualize_rdb.py data/TPCDS/parsed
```

This creates `er_diagram.{md,html}` and `referential_dependencies.{md,json}` under `parsed/viz/`. This step is not required by benchmark generation, but it is useful for catching missing keys or incorrectly parsed relationships.

### 4. Create benchmark configs for a new dataset

Copy the three Chinook YAML files into the new dataset directory, then update at least these fields:

```yaml
benchmark:
  name: MONDIAL_small
  source_database: MONDIAL
  size_level: small
  source_path: data/MONDIAL/parsed
  output_dir: data/MONDIAL/benchmarks/small
```

Also review:

- `size.after_table_count`: must fit the number and connectivity of parsed tables.
- `case_counts`: number of `extend_table`, `create_table`, and `insert_table` cases.
- `after_context.max_fk_depth`: how far connected context may expand through foreign keys.
- `sample_row_count`: must be compatible with the available rows.
- `case_rules`: eligibility rules for source tables and incoming columns.
- `perturbation`: alias-based renaming and column-order shuffling.

Use different `name`, `size_level`, and `output_dir` values in the medium and large configs.

### 5. Generate benchmark cases

For Chinook:

```bash
python data/form_benchmark.py data/Chinook/configs/small.yaml
python data/form_benchmark.py data/Chinook/configs/medium.yaml
python data/form_benchmark.py data/Chinook/configs/large.yaml
```

For MONDIAL, after completing steps 1-4:

```bash
python data/form_benchmark.py data/MONDIAL/configs/small.yaml
python data/form_benchmark.py data/MONDIAL/configs/medium.yaml
python data/form_benchmark.py data/MONDIAL/configs/large.yaml
```

For TPC-DS, after the Qwen3-8B profile has been generated and the row-loading
policy has been validated:

```bash
python data/form_benchmark.py data/TPCDS/configs/small.yaml
python data/form_benchmark.py data/TPCDS/configs/medium.yaml
python data/form_benchmark.py data/TPCDS/configs/large.yaml
```

Warning: generating a size level replaces its configured `output_dir` before rebuilding all `case_XXXX` directories. Keep manual files outside generated benchmark directories.

## Quick checklist for adding another raw dataset

- The raw file contains both PostgreSQL-compatible DDL and row inserts.
- Parsing reports non-zero table and row counts.
- Primary and foreign keys in `constraints.json` match the source database.
- Every required table has a CSV in `parsed/tables/`.
- Profiling has produced `parsed/profiles.json`.
- The ER/dependency report looks reasonable.
- Dataset-specific YAML configs point to the correct parsed and output directories.
- Small, medium, and large benchmark generation completes with the intended case counts.
