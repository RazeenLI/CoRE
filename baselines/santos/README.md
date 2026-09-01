# SANTOS baseline

This baseline ports the synthesized-KB path of SANTOS to the project's current
Python/Pandas stack. For every case it constructs column-value and column-pair
relationship indexes from only the current existing RDB, queries them with the
incoming table, applies maximum-weight bipartite column matching, and converts
the evidence with the shared deterministic evolution rules.

The implementation does not use YAGO. Index construction is intentionally
repeated and included in end-to-end latency. This is an adaptation of SANTOS,
not a claim that the original system emits RDB evolution operations.

Original implementation: https://github.com/northeastern-datalab/santos
(BSD-3-Clause). Cite the SANTOS SIGMOD/PACMMOD 2023 paper.
