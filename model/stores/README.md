# `stores/`

The `stores/` directory contains persistent or semi-persistent system state.

## `schema_registry.py`

Stores the current existing RDB schema.

Example:

```json
{
  "tables": {
    "Customer": {
      "columns": {
        "CustomerId": {
          "type": "integer",
          "role": "primary_key"
        },
        "Email": {
          "type": "string"
        }
      },
      "primary_key": ["CustomerId"],
      "foreign_keys": []
    }
  }
}
```

## `metadata_catalog.py`

Stores semantic metadata for tables and columns.

Example:

```json
{
  "Customer.Email": {
    "semantic_type": "email",
    "description": "Email address identifying a customer",
    "aliases": ["client_email", "contact_email"]
  }
}
```

## `constraint_catalog.py`

Stores schema-level constraints.

Examples:

```
primary keys
foreign keys
unique constraints
domain constraints
functional dependencies
```

The first version can focus only on primary keys and foreign keys.

## `embedding_index.py`

Stores table and column embeddings.

The Matcher Agent uses this index to retrieve the most relevant target tables and columns for an incoming table.

Example entries:

```
Customer
Customer.Email
Invoice.Total
Track.Name
```

## `mapping_memory.py`

Stores previously accepted and rejected mappings.

Example:

```json
{
  "accepted": [
    {
      "source_alias": "client_email",
      "target": "Customer.Email"
    }
  ],
  "rejected": [
    {
      "source_alias": "total_spend",
      "target": "Customer.total_spend",
      "reason": "Derived aggregate attribute"
    }
  ]
}
```

## `decision_log.py`

Stores system decisions for debugging and evaluation.

Example:

```json
{
  "run_id": "run_001",
  "case_id": "chinook_case_001",
  "decision_type": "extend_existing_table",
  "target_table": "Customer",
  "validation_status": "pass"
}
```

# 