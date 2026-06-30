# `validators/`

The `validators/` directory contains schema-level checking modules used by the Validator Agent.

## `type_checker.py`

Checks whether proposed source-target column mappings are type-compatible.

## `key_checker.py`

Checks whether a proposed primary key or candidate key is reasonable.

Example:

```
If the system proposes InvoiceId as the primary key of Invoice,
the checker verifies whether InvoiceId is unique in the incoming table sample.
```

## `fk_checker.py`

Checks whether a proposed foreign key is structurally valid.

Example:

```
Invoice.CustomerId → Customer.CustomerId
```

The checker verifies:

```
the referenced table exists
the referenced column exists
the referenced column is a key
the source values have reasonable overlap with target key values
```

## `domain_checker.py`

Checks simple domain constraints.

Example:

```
loyalty_tier values are {bronze, silver, gold}
```

## `fd_checker.py`

Checks functional-dependency-like signals.

This is useful for deciding whether an incoming column should be added to an existing table.

Example:

```
customer_id → loyalty_tier
```

If this dependency holds, `loyalty_tier` may be a valid scalar attribute of `Customer`.

## `normalization_checker.py`

Checks whether the proposed schema design is likely to violate basic normalization principles.

Example:

```
preference_type and preference_value should probably not be added directly to Customer if each customer can have multiple preferences.
```

## `routing_rules.py`

Decides where to route a failed validation.

Example:

```
mapping_error → Matcher Agent
schema_design_error → Evolution Agent
profile_error → Profiler Agent
low_evidence → Human Review
```

# 