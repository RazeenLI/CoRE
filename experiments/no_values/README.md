# No Sample Values experiment

Pipeline:

```text
Profiler -> MPNet Candidate Selector -> Evolutor -> Validator -> Decision
```

This is a single-variable Standard variant for deployments where raw database
cell values cannot be provided to model components. The Profiler, Selector,
and Evolutor receive empty incoming/existing sample-value collections. Schema,
constraints, and non-literal profiles remain available. The Validator already
uses only proposals, schemas, and constraints.

Real tuples remain inside TaskState and are used by proposal application and
the final database update. The experiment therefore changes model evidence,
not the integration task or saved database contents.

```bash
GPU_IDS=0,1 MODEL=no_values DATASET=Chinook DATASIZE=large ./run_cases.sh
```
