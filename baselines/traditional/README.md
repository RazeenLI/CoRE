# JL and COMA rule baselines

Both baselines use the current pure-Python implementations in Valentine and
share the same deterministic operation and proposal pipeline. They do not load
an LLM or embedding model.

- `jl`: instance-based Jaccard column similarity with Levenshtein value
  equality, followed by Hungarian one-to-one assignment.
- `coma`: hybrid COMA matching with schema signals and TF-IDF instance signals,
  followed by Hungarian one-to-one assignment.

After matching, both baselines apply the same key-aware rules for
`insert_table`, `extend_table`, and `create_table`, then use the project's
existing rule-based proposal builder.

Install:

```bash
python -m pip install -r baselines/traditional/requirements.txt
```

Run:

```bash
MODEL=jl DATASIZE=large ./run_cases.sh
MODEL=coma DATASIZE=large ./run_cases.sh
```

Matcher-specific and shared rule thresholds are under `jl`, `coma`, and
`traditional` in the agent YAML. Tune them only on development data.
