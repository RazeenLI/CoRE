# Operation-validity annotation

This experiment audits whether operation-level disagreements between CoRE and
the benchmark reference admit more than one reasonable evolution decision.
Annotators see only the existing RDB and the incoming table. They may select
one or more of Insert, Extend, and Create.

Generate the fixed 100-case manifest and the self-contained HTML:

```bash
python -m experiments.alternative_validity.build_annotation
```

The generator reads `save/<dataset>/standard/<size>/<case>/proposal.json`.
Run it again after replacing those outputs with the final corrected runs.

Send only `annotation.html` to annotators. Their choices are autosaved in the
browser and exported with the **Export JSON** button. Collect the JSON files in
one directory and analyze them with:

```bash
python -m experiments.alternative_validity.analyze_annotations \
  --responses path/to/exported/json/files \
  --output experiments/alternative_validity/analysis
```

The HTML deliberately contains neither reference nor CoRE decisions. Those
labels remain only in `selected_cases.json`, which must not be sent to
annotators.
