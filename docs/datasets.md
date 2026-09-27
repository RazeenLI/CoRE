# Datasets

CoRE includes benchmark cases derived from four database sources:

- Chinook
- MONDIAL
- TPC-DS
- Spider

It also includes continuous-evolution sequences derived from the benchmark
construction process. The committed cases are part of the research artifact
and are intentionally versioned even though they account for most repository
files.

For the complete directory format, source preparation commands, construction
rules, and dataset statistics, see [Dataset preparation](../data/README.md).

For source licenses, attribution, redistribution notes, and local
modifications, see [Dataset licenses](../DATA_LICENSES.md).

## Raw sources

Do not add generated TPC-DS `.dat` files or complete third-party tool archives
to Git. Download source tools from their official publishers and generate raw
rows locally. The repository's `.gitignore` excludes generated raw-data
directories.

## Benchmark availability

Each committed case contains the existing database, incoming table, expected
proposal, and expected database state required for offline evaluation. This
allows artifact reviewers to inspect and evaluate the benchmark without
regenerating every source database.
