# `agents/`

The `agents/` directory contains the main decision-making components of the pipeline.

## `profiler_agent.py`

The Profiler Agent analyzes the incoming table.

It extracts information such as:

```
column names
inferred data types
sample values
null rate
distinct ratio
candidate key signals
semantic column descriptions
table-level summary
```

Example output:
```json
{
  "table_summary": "Customer loyalty information",
  "columns": [
    {
      "name": "client_email",
      "type": "string",
      "semantic_type": "email",
      "description": "Email address identifying a customer"
    },
    {
      "name": "loyalty_tier",
      "type": "string",
      "semantic_type": "membership_level",
      "description": "Customer loyalty membership level"
    }
  ]
}
```

## `matcher_agent.py`

The Matcher Agent compares the incoming table against the existing RDB schema.

It performs:

```
table-level matching
column-level matching
candidate target table ranking
confidence scoring
unmatched column detection
```

Example output:

```json
{
  "best_target_table": "Customer",
  "table_match_confidence": 0.82,
  "column_mappings": [
    {
      "source_column": "client_email",
      "target_column": "Customer.Email",
      "confidence": 0.93
    }
  ],
  "unmatched_source_columns": ["loyalty_tier"],
  "route": "evolution"
}
```

## `evolution_agent.py`

The Evolution Agent decides how the schema should change when the incoming table cannot be fully matched to the existing schema.

It predicts one of the following schema-level decisions:

```
match_existing_table
extend_existing_table
create_new_table
create_association_table
reject
human_review
```

Example output:

```json
{
  "evolution_type": "extend_existing_table",
  "target_table": "Customer",
  "schema_operations": [
    {
      "operation": "add_column",
      "table": "Customer",
      "column": "loyalty_tier",
      "type": "string"
    }
  ]
}
```

## `validator_agent.py`

The Validator Agent checks whether the proposed mapping or schema evolution is structurally reasonable.

It does not execute SQL. Instead, it performs schema-level validation, such as:

```
type compatibility checking
duplicate column checking
primary key checking
foreign key structure checking
candidate key checking
basic normalization checking
failure routing
```

Example successful validation:

```json
{
  "status": "pass",
  "validation_confidence": 0.88,
  "route": "final_decision"
}
```

Example failed validation:

```json
{
  "status": "fail",
  "failure_type": "mapping_error",
  "route_back_to": "matcher",
  "reason": "The source column region was mapped to Customer.country, but the values appear to represent states."
}
```

## `final_decision_agent.py`

The Final Decision Agent converts the validated proposal into the final structured output.

Example output:

```json
{
  "decision_type": "extend_existing_table",
  "target_table": "Customer",
  "schema_operations": [
    {
      "operation": "add_column",
      "table": "Customer",
      "column": "loyalty_tier",
      "type": "string"
    }
  ],
  "column_mappings": [
    {
      "source_column": "client_email",
      "target_column": "Customer.Email",
      "role": "lookup"
    },
    {
      "source_column": "loyalty_tier",
      "target_column": "Customer.loyalty_tier",
      "role": "new_column"
    }
  ]
}
```

## `memory_update_agent.py`

The Memory Update Agent updates the system state after a final decision.

It updates:

```
schema registry
metadata catalog
embedding index
accepted mappings
rejected mappings
decision log
```

For example, if the system decides to extend the Customer table with loyalty_tier, this agent updates the schema registry and records the accepted mapping.