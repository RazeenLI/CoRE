# Evaluation metric roadmap

This document tracks implemented and planned evaluation dimensions. `DONE`
means the unified evaluator or a dedicated experiment implements the metric;
`DERIVABLE` means current outputs contain the required information; `PARTIAL`
means only part of the intended analysis exists; and `TODO` is not yet
implemented.

## Coverage and run health

| Metric | Status | Purpose |
|---|---|---|
| Result coverage | DONE | Separates missing outputs from semantic errors. |
| Pipeline success rate | DONE | Distinguishes completed workflows from residual evaluable outputs. |
| Load/parse failure rate | DONE | Exposes malformed or damaged outputs separately. |

## Operation decision

| Metric | Status | Purpose |
|---|---|---|
| Decision accuracy and Macro-F1 | DONE | Evaluates `insert`, `extend`, and `create` without majority-class dominance. |
| Per-class precision/recall/F1 | DONE | Shows operation-specific over- and under-prediction. |
| Confusion matrix and create-to-extend rate | DONE | Identifies directional operation errors. |

## Decision and action quality

| Metric | Status | Purpose |
|---|---|---|
| Action F1 conditioned on decision correctness | DONE | Separates outer operation errors from proposal-construction errors. |
| Correct-decision/wrong-action rate | DONE | Finds cases where the operation is right but implementation is wrong. |
| Wrong-decision/useful-action rate | DONE | Captures partially useful proposals under a wrong operation label. |
| Decision-action consistency | DONE | Checks that action shapes agree with the selected operation. |
| Operation-only proposal F1 | DONE | Avoids counting the decision fact twice. |

## Placement and proposal structure

| Metric | Status | Purpose |
|---|---|---|
| Target-table accuracy | DONE | Evaluates the chosen existing target relation. |
| Column placement precision/recall/F1 | DONE | Evaluates source-to-target placement facts. |
| Exact column-placement accuracy | DONE | Requires every placement in a case to match. |
| Proposal fact micro/macro F1 | DONE | Jointly evaluates decision, table, and column facts. |
| Table-action and column-action exact match | DONE | Prevents large fact sets from hiding structural errors. |

## Constraints and final database state

| Metric | Status | Purpose |
|---|---|---|
| Primary-key and foreign-key F1 | DONE | Evaluates expected constraints directly. |
| Constraint exact match | DONE | Requires a complete constraint-set match. |
| Broken-FK count/rate | DONE | Measures structural validity independently of semantic correctness. |
| Final schema exact match | DONE | Detects proposal-application errors. |
| Final constraint exact/F1 | DONE | Evaluates the applied database rather than proposal actions alone. |
| Tuple incorporation accuracy | DONE | Checks multiset coverage of incoming rows at reference placements. |
| Value transformation accuracy | TODO | Reserved for rename, cast, deduplication, and value transformations. |

## Completeness, validity, and preservation

| Metric | Status | Purpose |
|---|---|---|
| Required-column coverage | DONE | Checks whether every incoming column is addressed. |
| Raw-valid and checked-valid rates | DONE | Evaluates proposal-only and applied-database validity. |
| Invalid reference, duplicate definition, and conflict rates | DONE | Attributes structural invalidity. |
| Non-target preservation score/rate | DONE | Measures collateral changes outside the intended target. |
| Unexpected table/column/FK modification rates | DONE | Localizes preservation failures. |

## Candidate retrieval

| Metric | Status | Purpose |
|---|---|---|
| Table and column Hit@K/MRR | DONE | Evaluates whether known targets survive retrieval. |
| Recall versus context size | TODO | Measures the retrieval/context trade-off. |
| End-to-end quality by Top-K | TODO | Tests whether higher retrieval recall improves proposals. |
| Retrieval-conditioned error rate | TODO | Separates retrieval misses from Evolutor errors. |
| Create-context evaluation | TODO | Requires neighborhood evidence rather than a unique target table. |

## Ambiguity and reference quality

| Metric | Status | Purpose |
|---|---|---|
| Cross-method decision agreement | DERIVABLE | Flags possible ambiguous cases without declaring the reference wrong. |
| Strict reference accuracy | DONE | Measures recovery of the benchmark reference. |
| Ambiguity-aware accuracy | TODO | Accepts multiple human-validated outcomes. |
| Human acceptability and agreement | TODO | Requires completed annotation analysis and agreement reporting. |

## Robustness slices

Dataset, context size, operation type, clean/perturbed status, and perturbation
type are implemented. Planned slices include composite-key width, relation
role, schema overlap, and sample-row count.

## Validator and revision loop

| Metric | Status | Purpose |
|---|---|---|
| Retry rate/count and exhaustion rate | DONE | Measures revision frequency and failure to converge. |
| Error detection precision/recall | PARTIAL | Final-proposal detection exists; per-round replay is pending. |
| False-accept and false-reject rates | DONE/PARTIAL | False rejection is incomplete when no final output exists. |
| Repair success and decision correction/harm | DONE | Measures whether retries fix or damage proposals. |
| No-change retry rate | DONE | Detects ineffective repeated revisions. |
| Feedback-routing accuracy | TODO | Evaluates whether feedback reaches the responsible agent. |

Validator model-size comparisons should replay identical proposals with fixed
prompts, decoding, and deterministic gates before running a full revision loop.
Planned comparisons include detection quality, false acceptance/rejection,
repair/harm, latency, tokens, agreement, and calibration.

## Efficiency and statistical reliability

End-to-end latency, per-stage latency, and retry cost are implemented. LLM call
count is partial; input/output tokens and peak context size remain planned.
Mean and standard deviation across repeated runs are supported, while bootstrap
confidence intervals and paired significance tests remain TODO. Greedy decoding
reduces randomness, but complete environment and version capture is still
required for fixed-seed reproducibility.

## Complexity analysis

The evaluator records existing/incoming attribute counts, relation-width
statistics, foreign-key counts and degrees, and composite-key counts and
widths. Quality buckets and complexity-quality correlations remain TODO.
Thresholds must be fixed before analysis, with case counts reported per bucket
and dataset, operation, and context size treated as potential confounders.

## Recommended primary table

At minimum, report result coverage, decision accuracy, decision Macro-F1,
target accuracy, column Micro-F1, operation-only proposal F1, constraint F1,
checked-valid rate, non-target full-preservation rate, and end-to-end latency.
Ambiguity, retrieval Top-K, Validator, robustness, and efficiency decompositions
belong in separate tables or figures.
