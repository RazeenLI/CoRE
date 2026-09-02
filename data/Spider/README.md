# Spider Dataset

Spider is a collection of independent cross-domain SQLite databases. Each
`raw/<database>/<database>.sqlite` file must be treated as one source RDB;
tables from different databases must never be merged into one benchmark case.

## Raw-data inventory

Read-only inspection on 2026-09-01 found:

| Statistic | Value |
|---|---:|
| SQLite databases | 166 |
| Tables | 873 |
| Columns | 4,497 |
| Primary-key columns | 949 |
| Foreign-key entries | 800 |
| Rows | 1,604,329 |
| Median tables per database | 4 |
| Mean tables per database | 5.26 |
| Maximum tables in one database | 26 |

The current benchmark sizes use 3--5, 6--9, and 10--15 context tables.
Eligibility before applying operation-specific filters is:

| Size | Minimum tables | Structurally eligible databases | Largest FK component reaches minimum |
|---|---:|---:|---:|
| Small | 3 | 143 | 138 |
| Medium | 6 | 52 | 49 |
| Large | 10 | 22 | 19 |

Nine databases contain at least one empty table, two expose no SQLite foreign
keys, and one exposes no primary key. In particular, `academic` and `imdb`
contain schema but no rows, so they cannot satisfy the current
`require_sample_rows` rule without a separate schema-only policy.

## Construction plan

1. Import every SQLite database independently into the common parsed-RDB
   representation, retaining `source_database` in case metadata.
2. Enumerate eligible `insert_table`, `extend_table`, and `create_table`
   candidates after applying the existing operation rules.
3. Construct source-centered sub-RDB contexts and classify the resulting cases
   by the shared 3--5, 6--9, and 10--15 table boundaries. Prefer FK neighbors
   when available, but do not require a create-table source or the entire
   context to be FK-connected.
4. Split and cap cases by source database so that one schema cannot dominate a
   size or appear in both prompt development and final evaluation.
5. Use 200/175/125 (Small/Medium/Large) as the provisional 500-case target,
   with a 20/40/40 percent Insert/Extend/Create split. Finalize it after
   inspecting the per-operation candidate inventory. Spider may reasonably
   contain more cases than each single-database source because it covers 166
   cross-domain schemas, but per-database contribution caps are still required.

Natural-language questions and gold SQL files from the original Text-to-SQL
task are not inputs to this benchmark.

## Preparation commands

Import every SQLite database into the common parsed-RDB representation:

```bash
python data/prepare_spider.py
```

If a batch was interrupted, resume without reparsing completed databases:

```bash
python data/prepare_spider.py --skip-existing
```

Import selected databases while testing:

```bash
python data/prepare_spider.py \
  --database wedding \
  --database academic
```

Profile all imported databases with one shared model load:

```bash
python data/profile_parsed_tables.py \
  --parsed-root data/Spider/parsed \
  --model-name Qwen/Qwen3.5-9B \
  --device-map auto \
  --sample-num 5 \
  --skip-existing
```

Use `--no-llm` for a deterministic compatibility check. The importer uses the
SQLite files as the authoritative source because all 166 databases provide
them and they contain both schema and rows. The available `schema.sql` files
are retained for validation rather than parsed as PostgreSQL input.

## Benchmark construction

First inspect operation-level eligibility after every database has a complete
`profiles.json`:

```bash
for size in small medium large; do
  python data/form_spider_benchmark.py \
    "data/Spider/configs/$size.yaml" \
    --inventory-only
done
```

The inventories are saved as `data/Spider/inventory_<size>.json`. Generate the
provisional 200/175/125 cases only after reviewing these files:

```bash
for size in small medium large; do
  python data/form_spider_benchmark.py \
    "data/Spider/configs/$size.yaml"
done
```

Generation refuses to replace a non-empty benchmark directory. Use
`--overwrite` only when intentionally rebuilding that size.
