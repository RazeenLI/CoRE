# Operation-validity annotation artifact

This directory preserves the blinded instrument and anonymized responses used
for the alternative-validity study.

- `annotation.html`: self-contained questionnaire shown to annotators.
- `selected_cases.json`: private-to-analysis manifest containing reference and
  predicted decisions; it was not shown to annotators.
- `responses/`: anonymized exported responses with free-text comments removed.

Regenerate the instrument from final standard-model outputs with:

```bash
python -m experiments.alternative_validity.build_annotation
```

Analyze the preserved responses with:

```bash
python -m experiments.alternative_validity.analyze_annotations \
  --responses artifacts/annotation/responses
```
