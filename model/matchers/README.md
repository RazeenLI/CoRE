# `matchers/`

The `matchers/` directory contains reusable matching algorithms used by the Matcher Agent.

## `lexical_matcher.py`

Computes name-based similarity.

Examples:

```
client_email ≈ Email
cust_id ≈ CustomerId
phone_number ≈ Phone
```

Possible methods:

```
token similarity
edit distance
substring matching
abbreviation matching
Jaccard similarity
```

## `type_matcher.py`

Checks whether source and target column types are compatible.

Examples:

```
string ↔ varchar: compatible
integer ↔ numeric: partially compatible
date_string ↔ datetime: transform needed
string ↔ integer: incompatible
```

## `value_matcher.py`

Compares sample values.

Examples:

```
incoming.client_id values overlap with Customer.CustomerId
incoming.email values follow the same pattern as Customer.Email
```

This module is useful for detecting possible foreign key relationships.

## `embedding_matcher.py`

Uses table and column embeddings to retrieve candidate matches.

Example:

```
incoming table embedding → top-k target tables
incoming column embedding → top-k target columns
```

## `score_fusion.py`

Combines multiple matching signals into a final score.

Example:

```
final_score =
  lexical_score * 0.3 +
  type_score * 0.2 +
  value_score * 0.2 +
  embedding_score * 0.3
```