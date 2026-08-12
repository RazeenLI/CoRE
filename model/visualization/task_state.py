from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Literal


MermaidMode = Literal["cdn", "code_only"]


def save_task_state_visualization(
    *,
    task_id: str,
    incoming_schema: dict[str, Any],
    incoming_values: Any,
    existing_schema: dict[str, Any],
    constraints: dict[str, Any],
    existing_values: Any,
    existing_profiles: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    trace: list[dict[str, Any]],
    save_path: str | Path,
    enable_mermaid: bool = True,
    mermaid_mode: MermaidMode = "cdn",
) -> dict[str, Path]:
    """
    Save TaskState visualization as Markdown and HTML.

    This visualizer is independent from Decision.
    Decision, RunState visualization, or external scripts can call it
    as long as they provide the required inputs.

    save_path is treated as a directory.

    Returns:
        {
            "markdown": Path(...),
            "html": Path(...),
        }
    """
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)

    safe_task_id = _safe_filename(task_id)

    md_path = save_dir / f"{safe_task_id}_task_state.md"
    html_path = save_dir / f"{safe_task_id}_task_state.html"

    md_content = build_task_state_markdown(
        task_id=task_id,
        incoming_schema=incoming_schema,
        incoming_values=incoming_values,
        existing_schema=existing_schema,
        constraints=constraints,
        existing_values=existing_values,
        existing_profiles=existing_profiles,
        results=results,
        trace=trace,
        enable_mermaid=enable_mermaid,
    )

    html_content = build_task_state_html(
        task_id=task_id,
        incoming_schema=incoming_schema,
        incoming_values=incoming_values,
        existing_schema=existing_schema,
        constraints=constraints,
        existing_values=existing_values,
        existing_profiles=existing_profiles,
        results=results,
        trace=trace,
        enable_mermaid=enable_mermaid,
        mermaid_mode=mermaid_mode,
    )

    md_path.write_text(md_content, encoding="utf-8")
    html_path.write_text(html_content, encoding="utf-8")

    return {
        "markdown": md_path,
        "html": html_path,
    }


def build_task_state_markdown(
    *,
    task_id: str,
    incoming_schema: dict[str, Any],
    incoming_values: Any,
    existing_schema: dict[str, Any],
    constraints: dict[str, Any],
    existing_values: Any,
    existing_profiles: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    trace: list[dict[str, Any]],
    enable_mermaid: bool = True,
) -> str:
    parts: list[str] = []

    parts.append(f"# TaskState Visualization: `{task_id}`")

    parts.append("\n## 1. Basic Information")

    parts.append("\n### Incoming Schema")
    parts.append(_schema_summary_md(incoming_schema))

    parts.append("\n### Incoming Sample Values")
    parts.append(_sample_values_md(schema=incoming_schema, values=incoming_values))

    parts.append("\n### Existing Schema")
    parts.append(_schema_summary_md(existing_schema))

    parts.append("\n### Existing Constraints")
    parts.append(_constraints_md(constraints, enable_mermaid=enable_mermaid))

    parts.append("\n### Existing Sample Values")
    parts.append(_sample_values_md(schema=existing_schema, values=existing_values))

    parts.append("\n### Existing Profiles")
    parts.append(_profiles_md(existing_profiles))

    parts.append("\n## 2. Pipeline Trace")

    for item in _iter_trace_results(trace=trace, results=results):
        parts.append(
            _trace_item_md(
                item,
                enable_mermaid=enable_mermaid,
            )
        )

    return "\n".join(parts).rstrip() + "\n"


def build_task_state_html(
    *,
    task_id: str,
    incoming_schema: dict[str, Any],
    incoming_values: Any,
    existing_schema: dict[str, Any],
    constraints: dict[str, Any],
    existing_values: Any,
    existing_profiles: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    trace: list[dict[str, Any]],
    enable_mermaid: bool = True,
    mermaid_mode: MermaidMode = "cdn",
) -> str:
    trace_html = "\n".join(
        _trace_item_html(
            item,
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )
        for item in _iter_trace_results(trace=trace, results=results)
    )

    mermaid_script = ""
    if enable_mermaid and mermaid_mode == "cdn":
        mermaid_script = """
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true });
</script>
"""

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>TaskState Visualization - {html.escape(task_id)}</title>
  {mermaid_script}
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 32px;
      line-height: 1.45;
      background: #fafafa;
      color: #222;
    }}

    h1, h2, h3, h4, h5 {{
      color: #111;
    }}

    code {{
      background: #f2f2f2;
      padding: 1px 4px;
      border-radius: 4px;
    }}

    .section {{
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
      margin: 16px 0;
    }}

    .sub-block {{
      margin: 12px 0 12px 18px;
      padding: 12px;
      border-left: 3px solid #e2e2e2;
      background: #fcfcfc;
    }}

    .result-block {{
      margin: 12px 0 12px 18px;
      padding: 12px;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      background: #fff;
    }}

    .trace-item {{
      border-left: 4px solid #ddd;
      padding-left: 14px;
      margin: 16px 0;
      background: #fff;
    }}

    .trace-body {{
      margin-left: 18px;
      padding-left: 12px;
      border-left: 2px dashed #ddd;
    }}

    .meta {{
      color: #555;
      font-size: 14px;
    }}

    .success {{
      color: #147a2e;
      font-weight: bold;
    }}

    .failed {{
      color: #b00020;
      font-weight: bold;
    }}

    .warning {{
      color: #9a6700;
      font-weight: bold;
    }}

    .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      background: #f0f0f0;
      font-size: 12px;
      margin-right: 4px;
    }}

    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 8px 0 16px 0;
      background: #fff;
    }}

    th, td {{
      border: 1px solid #ddd;
      padding: 6px 8px;
      vertical-align: top;
      font-size: 14px;
    }}

    th {{
      background: #f0f0f0;
      text-align: left;
    }}

    pre {{
      background: #f6f8fa;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 12px;
      overflow-x: auto;
      font-size: 13px;
    }}

    details {{
      margin: 10px 0;
    }}

    summary {{
      cursor: pointer;
      font-weight: bold;
    }}

    .mermaid {{
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 12px;
      margin: 12px 0;
    }}
  </style>
</head>
<body>
  <h1>TaskState Visualization: <code>{html.escape(task_id)}</code></h1>

  <h2>1. Basic Information</h2>

  <div class="section">
    <h3>Incoming Schema</h3>
    {_schema_summary_html(incoming_schema)}
  </div>

  <div class="section">
    <h3>Incoming Sample Values</h3>
    {_sample_values_html(schema=incoming_schema, values=incoming_values)}
  </div>

  <div class="section">
    <h3>Existing Schema</h3>
    {_schema_summary_html(existing_schema)}
  </div>

  <div class="section">
    <h3>Existing Constraints</h3>
    {_constraints_html(
        constraints,
        enable_mermaid=enable_mermaid,
        mermaid_mode=mermaid_mode,
    )}
  </div>

  <div class="section">
    <h3>Existing Sample Values</h3>
    {_sample_values_html(schema=existing_schema, values=existing_values)}
  </div>

  <div class="section">
    <h3>Existing Profiles</h3>
    {_profiles_html(existing_profiles)}
  </div>

  <h2>2. Pipeline Trace</h2>

  <div class="section">
    {trace_html}
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------


def _iter_trace_results(
    *,
    trace: list[dict[str, Any]],
    results: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Build ordered trace items.

    Important:
    - trace controls display order
    - save_result events use data.result_index to fetch results[step][index]
    """
    items: list[dict[str, Any]] = []

    for order, event in enumerate(trace, start=1):
        step = event.get("step")
        event_type = event.get("event")
        data = event.get("data") or {}

        result = None
        result_missing = False

        if event_type == "save_result":
            result_index = data.get("result_index")

            if isinstance(step, str) and isinstance(result_index, int):
                step_results = results.get(step, [])

                if 0 <= result_index < len(step_results):
                    result = step_results[result_index]
                else:
                    result_missing = True
            else:
                result_missing = True

        items.append(
            {
                "order": order,
                "event": event,
                "result": result,
                "result_missing": result_missing,
            }
        )

    return items


def _trace_item_md(
    item: dict[str, Any],
    *,
    enable_mermaid: bool,
) -> str:
    event = item["event"]

    step = str(event.get("step", "unknown"))
    event_type = str(event.get("event", "unknown"))
    status = str(event.get("status", "unknown"))
    message = event.get("message", "")

    parts = [
        f"\n### {item['order']}. `{step}` / `{event_type}`",
        f"- status: `{status}`",
    ]

    if message:
        parts.append(f"- message: {message}")

    data = event.get("data")
    if data:
        parts.append("\n#### Trace Data")
        parts.append(_json_block_md(data))

    if item["result"] is not None:
        parts.append("\n#### Step Result")
        parts.append(
            _render_step_result_md(
                step=step,
                result=item["result"],
                enable_mermaid=enable_mermaid,
            )
        )

    if item["result_missing"]:
        parts.append("\n#### Step Result")
        parts.append("_Result missing._")

    return "\n".join(parts)


def _trace_item_html(
    item: dict[str, Any],
    *,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    event = item["event"]

    step = str(event.get("step", "unknown"))
    event_type = str(event.get("event", "unknown"))
    status = str(event.get("status", "unknown"))
    message = str(event.get("message", ""))

    status_class = _status_class(status)

    parts = [
        "<details class='trace-item' open>",
        (
            f"<summary>{item['order']}. "
            f"{html.escape(step)} / {html.escape(event_type)}</summary>"
        ),
        "<div class='trace-body'>",
        (
            f"<p class='meta'>status: "
            f"<span class='{status_class}'>{html.escape(status)}</span></p>"
        ),
    ]

    if message:
        parts.append(f"<p>{html.escape(message)}</p>")

    data = event.get("data")
    if data:
        parts.append(_json_details_html("trace_data", data))

    if item["result"] is not None:
        parts.append("<div class='result-block'>")
        parts.append(
            _render_step_result_html(
                step=step,
                result=item["result"],
                enable_mermaid=enable_mermaid,
                mermaid_mode=mermaid_mode,
            )
        )
        parts.append("</div>")

    if item["result_missing"]:
        parts.append("<p class='failed'>Result missing.</p>")

    parts.append("</div>")
    parts.append("</details>")

    return "\n".join(parts)


def _render_step_result_md(
    *,
    step: str,
    result: Any,
    enable_mermaid: bool,
) -> str:
    if not isinstance(result, dict):
        return _json_block_md(result)

    if step == "profiler":
        return _profile_md(result)

    if step == "matcher":
        return _matcher_md(result, enable_mermaid=enable_mermaid)

    if step in {"evolutor", "evolution"}:
        return _evolutor_md(result)

    if step == "proposal":
        return _proposal_md(result, enable_mermaid=enable_mermaid)

    if step == "preview":
        return _preview_md(result, enable_mermaid=enable_mermaid)

    if step == "validator":
        return _validator_md(result)

    if step == "decision":
        return _decision_md(result)

    return _json_block_md(result)


def _render_step_result_html(
    *,
    step: str,
    result: Any,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    if not isinstance(result, dict):
        return _json_details_html("step_result", result, open_by_default=True)

    if step == "profiler":
        return _profile_html(result)

    if step == "matcher":
        return _matcher_html(
            result,
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )

    if step in {"evolutor", "evolution"}:
        return _evolutor_html(result)

    if step == "proposal":
        return _proposal_html(
            result,
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )

    if step == "preview":
        return _preview_html(
            result,
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )

    if step == "validator":
        return _validator_html(result)

    if step == "decision":
        return _decision_html(result)

    return _json_details_html("step_result", result, open_by_default=True)


# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------


def _schema_summary_md(schema: dict[str, Any]) -> str:
    database = schema.get("database", "")
    tables = schema.get("tables", {})

    parts: list[str] = []

    if database:
        parts.append(f"- database: `{database}`")

    parts.append(f"- table_count: `{len(tables)}`")

    for table_name, table in tables.items():
        columns = table.get("columns", {})
        column_order = table.get("column_order") or list(columns.keys())

        parts.append(f"\n#### Table `{table_name}`")
        parts.append(f"- column_count: `{len(columns)}`")
        parts.append("")
        parts.append("| column | type | nullable | details |")
        parts.append("|---|---|---|---|")

        for column_name in column_order:
            column = columns.get(column_name, {})
            dtype = column.get("type_raw") or column.get("type") or ""
            nullable = column.get("nullable", "")

            details = []
            for key in ["max_length", "precision", "scale"]:
                if key in column:
                    details.append(f"{key}={column[key]}")

            parts.append(
                "| "
                f"`{_md_cell(column_name)}` | "
                f"`{_md_cell(dtype)}` | "
                f"`{_md_cell(nullable)}` | "
                f"{_md_cell(', '.join(details))} |"
            )

    return "\n".join(parts)


def _schema_summary_html(schema: dict[str, Any]) -> str:
    database = schema.get("database", "")
    tables = schema.get("tables", {})

    parts: list[str] = []

    if database:
        parts.append(f"<p class='meta'>database: <code>{html.escape(str(database))}</code></p>")

    parts.append(f"<p class='meta'>table_count: <code>{len(tables)}</code></p>")

    for table_name, table in tables.items():
        columns = table.get("columns", {})
        column_order = table.get("column_order") or list(columns.keys())

        rows = []

        for column_name in column_order:
            column = columns.get(column_name, {})
            dtype = column.get("type_raw") or column.get("type") or ""
            nullable = column.get("nullable", "")

            details = []
            for key in ["max_length", "precision", "scale"]:
                if key in column:
                    details.append(f"{key}={column[key]}")

            rows.append(
                "<tr>"
                f"<td><code>{html.escape(str(column_name))}</code></td>"
                f"<td><code>{html.escape(str(dtype))}</code></td>"
                f"<td><code>{html.escape(str(nullable))}</code></td>"
                f"<td>{html.escape(', '.join(details))}</td>"
                "</tr>"
            )

        parts.append(f"<h4>Table <code>{html.escape(str(table_name))}</code></h4>")
        parts.append(f"<p class='meta'>column_count: <code>{len(columns)}</code></p>")
        parts.append(
            "<table>"
            "<thead><tr>"
            "<th>column</th>"
            "<th>type</th>"
            "<th>nullable</th>"
            "<th>details</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Sample values
# ---------------------------------------------------------------------


def _sample_values_md(
    *,
    schema: dict[str, Any],
    values: Any,
) -> str:
    values_by_table = _normalize_values_by_table(schema=schema, values=values)
    tables = schema.get("tables", {})

    parts: list[str] = []

    for table_name, rows in values_by_table.items():
        table_schema = tables.get(table_name, {})
        column_order = table_schema.get("column_order")

        if not column_order and isinstance(rows, list) and rows:
            if isinstance(rows[0], dict):
                column_order = list(rows[0].keys())

        parts.append(f"#### Table `{table_name}`")

        if isinstance(rows, list):
            parts.append(_rows_md(rows, column_order=column_order))
        else:
            parts.append(_json_block_md(rows))

    return "\n\n".join(parts)


def _sample_values_html(
    *,
    schema: dict[str, Any],
    values: Any,
) -> str:
    values_by_table = _normalize_values_by_table(schema=schema, values=values)
    tables = schema.get("tables", {})

    parts: list[str] = []

    for table_name, rows in values_by_table.items():
        table_schema = tables.get(table_name, {})
        column_order = table_schema.get("column_order")

        if not column_order and isinstance(rows, list) and rows:
            if isinstance(rows[0], dict):
                column_order = list(rows[0].keys())

        parts.append(f"<h4>Table <code>{html.escape(str(table_name))}</code></h4>")

        if isinstance(rows, list):
            parts.append(_rows_html(rows, column_order=column_order))
        else:
            parts.append(_json_details_html(str(table_name), rows, open_by_default=True))

    return "\n".join(parts)


def _normalize_values_by_table(
    *,
    schema: dict[str, Any],
    values: Any,
) -> dict[str, Any]:
    """
    Normalize sample values into:
        table_name -> list[row dict]

    Supports:
    - incoming_values as list[dict]
    - existing_values as dict[str, list[dict]]
    """
    tables = schema.get("tables", {})

    if isinstance(values, dict):
        if all(isinstance(v, list) for v in values.values()):
            return values

        if "tables" in values and isinstance(values["tables"], dict):
            return values["tables"]

    if isinstance(values, list):
        table_names = list(tables.keys())
        if len(table_names) == 1:
            return {
                table_names[0]: values,
            }

        return {
            "values": values,
        }

    return {
        "values": values,
    }


def _rows_md(
    rows: list[Any],
    *,
    column_order: list[str] | None = None,
) -> str:
    if not rows:
        return "_No sample values._"

    if not isinstance(rows[0], dict):
        return _json_block_md(rows)

    columns = column_order or list(rows[0].keys())

    parts: list[str] = []
    parts.append("| " + " | ".join(_md_cell(col) for col in columns) + " |")
    parts.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for row in rows:
        parts.append(
            "| "
            + " | ".join(_md_cell(row.get(col, "")) for col in columns)
            + " |"
        )

    return "\n".join(parts)


def _rows_html(
    rows: list[Any],
    *,
    column_order: list[str] | None = None,
) -> str:
    if not rows:
        return "<p><em>No sample values.</em></p>"

    if not isinstance(rows[0], dict):
        return _json_details_html("rows", rows, open_by_default=True)

    columns = column_order or list(rows[0].keys())

    header = "".join(
        f"<th>{html.escape(str(col))}</th>"
        for col in columns
    )

    body_rows = []

    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(col, '')))}</td>"
            for col in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        "<table>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


# ---------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------


def _constraints_md(
    constraints: dict[str, Any],
    *,
    enable_mermaid: bool,
) -> str:
    if not constraints:
        return "_No constraints._"

    parts: list[str] = []

    if enable_mermaid:
        parts.append("```mermaid")
        parts.append(_constraints_mermaid(constraints))
        parts.append("```")

    parts.append(_constraints_tables_md(constraints))

    return "\n\n".join(parts)


def _constraints_html(
    constraints: dict[str, Any],
    *,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    if not constraints:
        return "<p><em>No constraints.</em></p>"

    parts: list[str] = []

    if enable_mermaid:
        parts.append(_mermaid_html(_constraints_mermaid(constraints), mode=mermaid_mode))

    parts.append(_constraints_tables_html(constraints))

    return "\n".join(parts)


def _constraint_body(constraints: dict[str, Any]) -> dict[str, Any]:
    return constraints.get("constraints", constraints)


def _constraints_mermaid(constraints: dict[str, Any]) -> str:
    body = _constraint_body(constraints)

    primary_keys = body.get("primary_keys", {}) or {}
    foreign_keys = body.get("foreign_keys", {}) or {}

    table_names = set(primary_keys.keys()) | set(foreign_keys.keys())

    for table_name, fks in foreign_keys.items():
        table_names.add(table_name)

        if isinstance(fks, list):
            for fk in fks:
                ref_table = fk.get("referenced_table")
                if ref_table:
                    table_names.add(ref_table)

    lines = ["flowchart LR"]

    if not table_names:
        lines.append('  empty["No table relationship constraints"]')
        return "\n".join(lines)

    for table_name in sorted(table_names):
        pk_cols = primary_keys.get(table_name, [])
        label = str(table_name)

        if pk_cols:
            label += "<br/>PK: " + ", ".join(map(str, pk_cols))

        lines.append(
            f'  {_mermaid_id(table_name)}["{_mermaid_label(label)}"]'
        )

    for table_name, fks in foreign_keys.items():
        if not isinstance(fks, list):
            continue

        for fk in fks:
            columns = ", ".join(map(str, fk.get("columns", [])))
            ref_table = fk.get("referenced_table", "")
            # ref_columns = ", ".join(map(str, fk.get("referenced_columns", [])))
            ref_columns = ", ".join(
                map(str, fk.get("referenced_columns") or [])
            )

            if not ref_table:
                continue

            edge_label = f"{columns} → {ref_table}.{ref_columns}"

            lines.append(
                f'  {_mermaid_id(table_name)} -->|"{_mermaid_label(edge_label)}"| {_mermaid_id(ref_table)}'
            )

    return "\n".join(lines)


def _constraints_tables_md(constraints: dict[str, Any]) -> str:
    body = _constraint_body(constraints)

    parts: list[str] = []

    primary_keys = body.get("primary_keys", {}) or {}
    foreign_keys = body.get("foreign_keys", {}) or {}
    unique_constraints = body.get("unique_constraints", {}) or {}
    indexes = body.get("indexes", {}) or {}

    parts.append("#### Primary Keys")
    if primary_keys:
        parts.append("| table | columns |")
        parts.append("|---|---|")
        for table, cols in primary_keys.items():
            parts.append(f"| `{_md_cell(table)}` | `{_md_cell(', '.join(map(str, cols)))}` |")
    else:
        parts.append("_None._")

    parts.append("\n#### Foreign Keys")
    if foreign_keys:
        parts.append("| table | columns | referenced_table | referenced_columns |")
        parts.append("|---|---|---|---|")
        for table, fks in foreign_keys.items():
            if not isinstance(fks, list):
                continue
            for fk in fks:
                parts.append(
                    "| "
                    f"`{_md_cell(table)}` | "
                    f"`{_md_cell(', '.join(map(str, fk.get('columns', []))))}` | "
                    f"`{_md_cell(fk.get('referenced_table', ''))}` | "
                    f"`{_md_cell(', '.join(map(str, fk.get('referenced_columns', []))))}` |"
                )
    else:
        parts.append("_None._")

    parts.append("\n#### Unique Constraints")
    if unique_constraints:
        parts.append(_json_block_md(unique_constraints))
    else:
        parts.append("_None._")

    parts.append("\n#### Indexes")
    if indexes:
        parts.append("| table | columns |")
        parts.append("|---|---|")
        for table, table_indexes in indexes.items():
            if not isinstance(table_indexes, list):
                continue
            for index_cols in table_indexes:
                parts.append(
                    f"| `{_md_cell(table)}` | `{_md_cell(', '.join(map(str, index_cols)))}` |"
                )
    else:
        parts.append("_None._")

    return "\n".join(parts)


def _constraints_tables_html(constraints: dict[str, Any]) -> str:
    body = _constraint_body(constraints)

    primary_keys = body.get("primary_keys", {}) or {}
    foreign_keys = body.get("foreign_keys", {}) or {}
    unique_constraints = body.get("unique_constraints", {}) or {}
    indexes = body.get("indexes", {}) or {}

    parts: list[str] = []

    parts.append("<h4>Primary Keys</h4>")
    if primary_keys:
        rows = []
        for table, cols in primary_keys.items():
            rows.append(
                "<tr>"
                f"<td><code>{html.escape(str(table))}</code></td>"
                f"<td><code>{html.escape(', '.join(map(str, cols)))}</code></td>"
                "</tr>"
            )
        parts.append(
            "<table>"
            "<thead><tr><th>table</th><th>columns</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    else:
        parts.append("<p><em>None.</em></p>")

    parts.append("<h4>Foreign Keys</h4>")
    if foreign_keys:
        rows = []
        for table, fks in foreign_keys.items():
            if not isinstance(fks, list):
                continue

            for fk in fks:
                rows.append(
                    "<tr>"
                    f"<td><code>{html.escape(str(table))}</code></td>"
                    f"<td><code>{html.escape(', '.join(map(str, fk.get('columns', []))))}</code></td>"
                    f"<td><code>{html.escape(str(fk.get('referenced_table', '')))}</code></td>"
                    f"<td><code>{html.escape(', '.join(map(str, fk.get('referenced_columns', []))))}</code></td>"
                    "</tr>"
                )

        parts.append(
            "<table>"
            "<thead><tr>"
            "<th>table</th>"
            "<th>columns</th>"
            "<th>referenced_table</th>"
            "<th>referenced_columns</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    else:
        parts.append("<p><em>None.</em></p>")

    parts.append("<h4>Unique Constraints</h4>")
    if unique_constraints:
        parts.append(_json_details_html("unique_constraints", unique_constraints))
    else:
        parts.append("<p><em>None.</em></p>")

    parts.append("<h4>Indexes</h4>")
    if indexes:
        rows = []
        for table, table_indexes in indexes.items():
            if not isinstance(table_indexes, list):
                continue

            for index_cols in table_indexes:
                rows.append(
                    "<tr>"
                    f"<td><code>{html.escape(str(table))}</code></td>"
                    f"<td><code>{html.escape(', '.join(map(str, index_cols)))}</code></td>"
                    "</tr>"
                )

        parts.append(
            "<table>"
            "<thead><tr><th>table</th><th>columns</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    else:
        parts.append("<p><em>None.</em></p>")

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------


def _profiles_md(profiles: dict[str, Any]) -> str:
    tables = profiles.get("tables")

    if isinstance(tables, dict):
        parts = []
        for table_name, profile in tables.items():
            parts.append(f"#### Profile: `{table_name}`")
            parts.append(_profile_md(profile))
        return "\n\n".join(parts)

    return _profile_md(profiles)


def _profiles_html(profiles: dict[str, Any]) -> str:
    tables = profiles.get("tables")

    if isinstance(tables, dict):
        parts = []
        for table_name, profile in tables.items():
            parts.append(f"<h4>Profile: <code>{html.escape(str(table_name))}</code></h4>")
            parts.append(_profile_html(profile))
        return "\n".join(parts)

    return _profile_html(profiles)


def _profile_md(profile: dict[str, Any]) -> str:
    table_profile = profile.get("table", {})
    columns = profile.get("columns", {})

    parts: list[str] = []

    parts.append("##### Table Profile")
    for key in ["name", "column_count", "entity", "role", "summary"]:
        if key in table_profile:
            parts.append(f"- {key}: `{_md_cell(table_profile[key])}`")

    aliases = table_profile.get("aliases", [])
    if aliases:
        parts.append(f"- aliases: `{_md_cell(', '.join(map(str, aliases)))}`")

    parts.append("\n##### Column Profiles")
    if not columns:
        parts.append("_No column profiles._")
        return "\n".join(parts)

    parts.append(
        "| column | dtype | semantic_type | business_concept | meaning | value_patterns | aliases |"
    )
    parts.append("|---|---|---|---|---|---|---|")

    for column_name, column in columns.items():
        parts.append(
            "| "
            f"`{_md_cell(column_name)}` | "
            f"`{_md_cell(column.get('dtype', ''))}` | "
            f"`{_md_cell(column.get('semantic_type', ''))}` | "
            f"`{_md_cell(column.get('business_concept', ''))}` | "
            f"{_md_cell(column.get('meaning', ''))} | "
            f"{_md_cell(', '.join(map(str, column.get('value_patterns', []))))} | "
            f"{_md_cell(', '.join(map(str, column.get('aliases', []))))} |"
        )

    return "\n".join(parts)


def _profile_html(profile: dict[str, Any]) -> str:
    table_profile = profile.get("table", {})
    columns = profile.get("columns", {})

    parts: list[str] = []

    parts.append("<div class='sub-block'>")
    parts.append("<h5>Table Profile</h5>")
    parts.append("<ul>")

    for key in ["name", "column_count", "entity", "role", "summary"]:
        if key in table_profile:
            parts.append(
                f"<li><b>{html.escape(key)}</b>: {html.escape(str(table_profile[key]))}</li>"
            )

    aliases = table_profile.get("aliases", [])
    if aliases:
        parts.append(
            f"<li><b>aliases</b>: {html.escape(', '.join(map(str, aliases)))}</li>"
        )

    parts.append("</ul>")
    parts.append("</div>")

    parts.append("<h5>Column Profiles</h5>")

    if not columns:
        parts.append("<p><em>No column profiles.</em></p>")
        return "\n".join(parts)

    rows = []
    for column_name, column in columns.items():
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(column_name))}</code></td>"
            f"<td>{html.escape(str(column.get('dtype', '')))}</td>"
            f"<td>{html.escape(str(column.get('semantic_type', '')))}</td>"
            f"<td>{html.escape(str(column.get('business_concept', '')))}</td>"
            f"<td>{html.escape(str(column.get('meaning', '')))}</td>"
            f"<td>{html.escape(', '.join(map(str, column.get('value_patterns', []))))}</td>"
            f"<td>{html.escape(', '.join(map(str, column.get('aliases', []))))}</td>"
            "</tr>"
        )

    parts.append(
        "<table>"
        "<thead><tr>"
        "<th>column</th>"
        "<th>dtype</th>"
        "<th>semantic_type</th>"
        "<th>business_concept</th>"
        "<th>meaning</th>"
        "<th>value_patterns</th>"
        "<th>aliases</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------


def _matcher_md(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
) -> str:
    matches = result.get("table_matches", [])

    if not matches:
        return "_No table matches._"

    parts: list[str] = []

    for i, match in enumerate(matches, start=1):
        target_table = match.get("target_table", "")
        confidence = match.get("confidence", "")
        status = match.get("match_status", "")
        reason = match.get("reason", "")

        parts.append(f"##### Match {i}: `{target_table}`")
        parts.append(f"- confidence: `{confidence}`")
        parts.append(f"- status: `{status}`")

        unmatched = match.get("unmatched_source_columns", [])
        ambiguous = match.get("ambiguous_source_columns", [])

        if unmatched:
            parts.append(f"- unmatched_source_columns: `{', '.join(map(str, unmatched))}`")

        if ambiguous:
            parts.append(f"- ambiguous_source_columns: `{', '.join(map(str, ambiguous))}`")

        if reason:
            parts.append(f"- reason: {reason}")

        if enable_mermaid:
            parts.append("\n```mermaid")
            parts.append(_matcher_mermaid(match, graph_id=f"match_{i}"))
            parts.append("```")

        parts.append(_matcher_columns_md(match))

    return "\n\n".join(parts)


def _matcher_html(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    matches = result.get("table_matches", [])

    if not matches:
        return "<p><em>No table matches.</em></p>"

    parts: list[str] = []

    for i, match in enumerate(matches, start=1):
        target_table = match.get("target_table", "")
        confidence = match.get("confidence", "")
        status = match.get("match_status", "")
        reason = match.get("reason", "")

        parts.append("<div class='sub-block'>")
        parts.append(f"<h4>Match {i}: <code>{html.escape(str(target_table))}</code></h4>")
        parts.append("<ul>")
        parts.append(f"<li><b>confidence</b>: {html.escape(str(confidence))}</li>")
        parts.append(f"<li><b>status</b>: {html.escape(str(status))}</li>")

        unmatched = match.get("unmatched_source_columns", [])
        ambiguous = match.get("ambiguous_source_columns", [])

        if unmatched:
            parts.append(
                f"<li><b>unmatched_source_columns</b>: "
                f"{html.escape(', '.join(map(str, unmatched)))}</li>"
            )

        if ambiguous:
            parts.append(
                f"<li><b>ambiguous_source_columns</b>: "
                f"{html.escape(', '.join(map(str, ambiguous)))}</li>"
            )

        if reason:
            parts.append(f"<li><b>reason</b>: {html.escape(str(reason))}</li>")

        parts.append("</ul>")

        if enable_mermaid:
            parts.append(
                _mermaid_html(
                    _matcher_mermaid(match, graph_id=f"match_{i}"),
                    mode=mermaid_mode,
                )
            )

        parts.append(_matcher_columns_html(match))
        parts.append("</div>")

    return "\n".join(parts)


def _matcher_columns_md(match: dict[str, Any]) -> str:
    column_matches = match.get("column_matches", {})

    if not column_matches:
        return "_No column matches._"

    parts = [
        "| source_column | target_column | confidence | reason |",
        "|---|---|---|---|",
    ]

    for source_column, candidates in column_matches.items():
        if not candidates:
            parts.append(
                f"| `{_md_cell(source_column)}` | _No reliable match_ |  |  |"
            )
            continue

        for candidate in candidates:
            parts.append(
                "| "
                f"`{_md_cell(source_column)}` | "
                f"`{_md_cell(candidate.get('target_column', ''))}` | "
                f"`{_md_cell(candidate.get('confidence', ''))}` | "
                f"{_md_cell(candidate.get('reason', ''))} |"
            )

    return "\n".join(parts)


def _matcher_columns_html(match: dict[str, Any]) -> str:
    column_matches = match.get("column_matches", {})

    if not column_matches:
        return "<p><em>No column matches.</em></p>"

    parts = [
        "<table>",
        "<thead><tr>"
        "<th>source_column</th>"
        "<th>target_column</th>"
        "<th>confidence</th>"
        "<th>reason</th>"
        "</tr></thead><tbody>",
    ]

    for source_column, candidates in column_matches.items():
        if not candidates:
            parts.append(
                "<tr>"
                f"<td><code>{html.escape(str(source_column))}</code></td>"
                "<td colspan='3'><em>No reliable match</em></td>"
                "</tr>"
            )
            continue

        for candidate in candidates:
            parts.append(
                "<tr>"
                f"<td><code>{html.escape(str(source_column))}</code></td>"
                f"<td><code>{html.escape(str(candidate.get('target_column', '')))}</code></td>"
                f"<td>{html.escape(str(candidate.get('confidence', '')))}</td>"
                f"<td>{html.escape(str(candidate.get('reason', '')))}</td>"
                "</tr>"
            )

    parts.append("</tbody></table>")

    return "\n".join(parts)


def _matcher_mermaid(match: dict[str, Any], graph_id: str) -> str:
    target_table = match.get("target_table", "target")
    column_matches = match.get("column_matches", {})

    src_prefix = _mermaid_id(f"{graph_id}_src")
    tgt_prefix = _mermaid_id(f"{graph_id}_tgt")

    lines = ["flowchart LR"]

    lines.append(f'  subgraph {src_prefix}["Incoming Columns"]')
    for source_column in column_matches.keys():
        lines.append(
            f'    {src_prefix}_{_mermaid_id(source_column)}["{_mermaid_label(source_column)}"]'
        )
    lines.append("  end")

    target_columns = []
    unmatched_sources = []

    for source_column, candidates in column_matches.items():
        if not candidates:
            unmatched_sources.append(source_column)

        for candidate in candidates:
            target_column = candidate.get("target_column")
            if target_column:
                target_columns.append(target_column)

    lines.append(f'  subgraph {tgt_prefix}["Target: {_mermaid_label(target_table)}"]')
    for target_column in sorted(set(target_columns)):
        lines.append(
            f'    {tgt_prefix}_{_mermaid_id(target_column)}["{_mermaid_label(target_column)}"]'
        )

    if unmatched_sources:
        lines.append(f'    {tgt_prefix}_NO_MATCH["No reliable match"]')

    lines.append("  end")

    for source_column, candidates in column_matches.items():
        source_id = f"{src_prefix}_{_mermaid_id(source_column)}"

        if not candidates:
            lines.append(f'  {source_id} -.->|no match| {tgt_prefix}_NO_MATCH')
            continue

        for candidate in candidates:
            target_column = candidate.get("target_column")
            confidence = candidate.get("confidence", "")

            if not target_column:
                continue

            target_id = f"{tgt_prefix}_{_mermaid_id(target_column)}"
            lines.append(
                f'  {source_id} -->|"{_mermaid_label(confidence)}"| {target_id}'
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Evolutor
# ---------------------------------------------------------------------


def _evolutor_md(result: dict[str, Any]) -> str:
    decision = result.get("decision", {})
    placements = result.get("column_placements", {})

    parts: list[str] = []

    if decision:
        parts.append("##### Evolution Decision")
        for key in ["decision_type", "target_table", "related_tables", "reason"]:
            if key in decision:
                value = decision[key]
                if isinstance(value, list):
                    value = ", ".join(map(str, value))
                parts.append(f"- {key}: `{_md_cell(value)}`")

    if result.get("reason"):
        parts.append(f"- reason: {result['reason']}")

    parts.append("\n##### Column Placements")

    if not placements:
        parts.append("_No column placements._")
        return "\n".join(parts)

    parts.append("| source_column | target_table | target_column | reason |")
    parts.append("|---|---|---|---|")

    for source_column, placement in placements.items():
        parts.append(
            "| "
            f"`{_md_cell(source_column)}` | "
            f"`{_md_cell(placement.get('target_table', ''))}` | "
            f"`{_md_cell(placement.get('target_column', ''))}` | "
            f"{_md_cell(placement.get('reason', ''))} |"
        )

    return "\n".join(parts)


def _evolutor_html(result: dict[str, Any]) -> str:
    decision = result.get("decision", {})
    placements = result.get("column_placements", {})

    parts: list[str] = []

    if decision:
        parts.append("<h4>Evolution Decision</h4>")
        parts.append("<ul>")
        for key in ["decision_type", "target_table", "related_tables", "reason"]:
            if key in decision:
                value = decision[key]
                if isinstance(value, list):
                    value = ", ".join(map(str, value))
                parts.append(
                    f"<li><b>{html.escape(key)}</b>: {html.escape(str(value))}</li>"
                )
        parts.append("</ul>")

    if result.get("reason"):
        parts.append(f"<p><b>reason</b>: {html.escape(str(result['reason']))}</p>")

    parts.append("<h4>Column Placements</h4>")

    if not placements:
        parts.append("<p><em>No column placements.</em></p>")
        return "\n".join(parts)

    rows = []

    for source_column, placement in placements.items():
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(source_column))}</code></td>"
            f"<td><code>{html.escape(str(placement.get('target_table', '')))}</code></td>"
            f"<td><code>{html.escape(str(placement.get('target_column', '')))}</code></td>"
            f"<td>{html.escape(str(placement.get('reason', '')))}</td>"
            "</tr>"
        )

    parts.append(
        "<table>"
        "<thead><tr>"
        "<th>source_column</th>"
        "<th>target_table</th>"
        "<th>target_column</th>"
        "<th>reason</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------


def _proposal_md(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
) -> str:
    parts: list[str] = []

    source_decision = result.get("source_decision")
    if source_decision:
        parts.append(f"- source_decision: `{source_decision}`")

    if enable_mermaid:
        parts.append("\n```mermaid")
        parts.append(_proposal_mermaid(result))
        parts.append("```")

    parts.append(_proposal_actions_table_md(result))

    constraint_actions = result.get("constraint_actions", [])
    if constraint_actions:
        parts.append("\n##### Constraint Actions")
        parts.append(_json_block_md(constraint_actions))

    return "\n".join(parts)


def _proposal_html(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    parts: list[str] = []

    source_decision = result.get("source_decision")
    if source_decision:
        parts.append(
            f"<p><b>source_decision</b>: {html.escape(str(source_decision))}</p>"
        )

    if enable_mermaid:
        parts.append(
            _mermaid_html(
                _proposal_mermaid(result),
                mode=mermaid_mode,
            )
        )

    parts.append(_proposal_actions_table_html(result))

    constraint_actions = result.get("constraint_actions", [])
    if constraint_actions:
        parts.append(_json_details_html("constraint_actions", constraint_actions))

    return "\n".join(parts)


def _proposal_mermaid(result: dict[str, Any]) -> str:
    table_actions = result.get("table_actions", [])

    lines = ["flowchart LR"]

    if not table_actions:
        lines.append('  empty["No proposal actions"]')
        return "\n".join(lines)

    for table_idx, table_action in enumerate(table_actions, start=1):
        target_table = table_action.get("table", f"target_{table_idx}")
        table_action_type = table_action.get("action", "")

        src_group = _mermaid_id(f"proposal_src_{table_idx}")
        tgt_group = _mermaid_id(f"proposal_tgt_{table_idx}")

        source_columns: list[str] = []
        target_columns: list[str] = []

        for column_action in table_action.get("column_actions", []):
            source_columns.extend(map(str, column_action.get("source_columns", [])))
            target_columns.extend(map(str, column_action.get("target_columns", [])))

        lines.append(f'  subgraph {src_group}["Incoming Columns"]')
        for source_column in sorted(set(source_columns)):
            lines.append(
                f'    {src_group}_{_mermaid_id(source_column)}["{_mermaid_label(source_column)}"]'
            )
        lines.append("  end")

        target_label = f"Target Table: {target_table}"
        if table_action_type:
            target_label += f" ({table_action_type})"

        lines.append(f'  subgraph {tgt_group}["{_mermaid_label(target_label)}"]')
        for target_column in sorted(set(target_columns)):
            lines.append(
                f'    {tgt_group}_{_mermaid_id(target_column)}["{_mermaid_label(target_column)}"]'
            )
        lines.append("  end")

        for column_action in table_action.get("column_actions", []):
            column_action_type = column_action.get("action", table_action_type)
            source_cols = column_action.get("source_columns", [])
            target_cols = column_action.get("target_columns", [])

            for source_column in source_cols:
                for target_column in target_cols:
                    lines.append(
                        f"  {src_group}_{_mermaid_id(source_column)} "
                        f'-->|"{_mermaid_label(column_action_type)}"| '
                        f"{tgt_group}_{_mermaid_id(target_column)}"
                    )

    return "\n".join(lines)


def _proposal_actions_table_md(result: dict[str, Any]) -> str:
    table_actions = result.get("table_actions", [])

    if not table_actions:
        return "_No table actions._"

    parts = [
        "| table | table_action | source_columns | column_action | target_columns |",
        "|---|---|---|---|---|",
    ]

    for table_action in table_actions:
        target_table = table_action.get("table", "")
        table_action_type = table_action.get("action", "")

        for column_action in table_action.get("column_actions", []):
            parts.append(
                "| "
                f"`{_md_cell(target_table)}` | "
                f"`{_md_cell(table_action_type)}` | "
                f"`{_md_cell(', '.join(map(str, column_action.get('source_columns', []))))}` | "
                f"`{_md_cell(column_action.get('action', ''))}` | "
                f"`{_md_cell(', '.join(map(str, column_action.get('target_columns', []))))}` |"
            )

    return "\n".join(parts)


def _proposal_actions_table_html(result: dict[str, Any]) -> str:
    table_actions = result.get("table_actions", [])

    if not table_actions:
        return "<p><em>No table actions.</em></p>"

    rows = []

    for table_action in table_actions:
        target_table = table_action.get("table", "")
        table_action_type = table_action.get("action", "")

        for column_action in table_action.get("column_actions", []):
            rows.append(
                "<tr>"
                f"<td><code>{html.escape(str(target_table))}</code></td>"
                f"<td>{html.escape(str(table_action_type))}</td>"
                f"<td>{html.escape(', '.join(map(str, column_action.get('source_columns', []))))}</td>"
                f"<td>{html.escape(str(column_action.get('action', '')))}</td>"
                f"<td>{html.escape(', '.join(map(str, column_action.get('target_columns', []))))}</td>"
                "</tr>"
            )

    return (
        "<table>"
        "<thead><tr>"
        "<th>table</th>"
        "<th>table_action</th>"
        "<th>source_columns</th>"
        "<th>column_action</th>"
        "<th>target_columns</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


# ---------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------


def _preview_md(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
) -> str:
    before = result.get("before", {})
    after = result.get("after", {})

    parts: list[str] = []

    parts.append("##### Before")
    parts.append("\n###### Schema")
    parts.append(_schema_summary_md(before.get("schema", {})))
    parts.append("\n###### Constraints")
    parts.append(_constraints_md(before.get("constraints", {}), enable_mermaid=enable_mermaid))

    parts.append("\n##### After")
    parts.append("\n###### Schema")
    parts.append(_schema_summary_md(after.get("schema", {})))
    parts.append("\n###### Constraints")
    parts.append(_constraints_md(after.get("constraints", {}), enable_mermaid=enable_mermaid))

    return "\n".join(parts)


def _preview_html(
    result: dict[str, Any],
    *,
    enable_mermaid: bool,
    mermaid_mode: MermaidMode,
) -> str:
    before = result.get("before", {})
    after = result.get("after", {})

    parts: list[str] = []

    parts.append("<h4>Before</h4>")
    parts.append("<div class='sub-block'>")
    parts.append("<h5>Schema</h5>")
    parts.append(_schema_summary_html(before.get("schema", {})))
    parts.append("<h5>Constraints</h5>")
    parts.append(
        _constraints_html(
            before.get("constraints", {}),
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )
    )
    parts.append("</div>")

    parts.append("<h4>After</h4>")
    parts.append("<div class='sub-block'>")
    parts.append("<h5>Schema</h5>")
    parts.append(_schema_summary_html(after.get("schema", {})))
    parts.append("<h5>Constraints</h5>")
    parts.append(
        _constraints_html(
            after.get("constraints", {}),
            enable_mermaid=enable_mermaid,
            mermaid_mode=mermaid_mode,
        )
    )
    parts.append("</div>")

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Validator / Decision
# ---------------------------------------------------------------------


def _validator_md(result: dict[str, Any]) -> str:
    parts: list[str] = []

    for key in ["route", "score", "summary"]:
        if key in result:
            parts.append(f"- {key}: `{_md_cell(result[key])}`")

    issues = result.get("issues", [])
    parts.append("- issues:")

    if issues:
        for issue in issues:
            parts.append(f"  - {_md_cell(issue)}")
    else:
        parts.append("  - none")

    return "\n".join(parts)


def _validator_html(result: dict[str, Any]) -> str:
    parts = ["<ul>"]

    for key in ["route", "score", "summary"]:
        if key in result:
            parts.append(
                f"<li><b>{html.escape(str(key))}</b>: "
                f"{html.escape(str(result[key]))}</li>"
            )

    issues = result.get("issues", [])
    parts.append("<li><b>issues</b>:")

    if issues:
        parts.append("<ul>")
        for issue in issues:
            parts.append(f"<li>{html.escape(str(issue))}</li>")
        parts.append("</ul>")
    else:
        parts.append(" none")

    parts.append("</li>")
    parts.append("</ul>")

    return "\n".join(parts)


def _decision_md(result: dict[str, Any]) -> str:
    parts = []

    for key in ["approved", "summary"]:
        if key in result:
            parts.append(f"- {key}: `{_md_cell(result[key])}`")

    if not parts:
        return _json_block_md(result)

    return "\n".join(parts)


def _decision_html(result: dict[str, Any]) -> str:
    parts = ["<ul>"]

    shown = False
    for key in ["approved", "summary"]:
        if key in result:
            shown = True
            parts.append(
                f"<li><b>{html.escape(str(key))}</b>: "
                f"{html.escape(str(result[key]))}</li>"
            )

    parts.append("</ul>")

    if not shown:
        return _json_details_html("decision", result, open_by_default=True)

    return "\n".join(parts)


# ---------------------------------------------------------------------
# Mermaid / JSON / Misc helpers
# ---------------------------------------------------------------------


def _mermaid_html(code: str, *, mode: MermaidMode) -> str:
    if mode == "cdn":
        return f"<pre class='mermaid'>{html.escape(code)}</pre>"

    return (
        "<details open>"
        "<summary>Mermaid source</summary>"
        f"<pre>{html.escape(code)}</pre>"
        "</details>"
    )


def _json_details_html(
    title: str,
    value: Any,
    *,
    open_by_default: bool = False,
) -> str:
    open_attr = " open" if open_by_default else ""

    return (
        f"<details{open_attr}>"
        f"<summary>{html.escape(title)}</summary>"
        f"<pre>{html.escape(_json_dumps(value))}</pre>"
        f"</details>"
    )


def _json_block_md(value: Any) -> str:
    return "```json\n" + _json_dumps(value) + "\n```"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _md_cell(value: Any) -> str:
    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")
    return text


def _safe_filename(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value or "task_state"


def _status_class(status: str) -> str:
    if status == "success":
        return "success"

    if status == "failed":
        return "failed"

    if status in {"warning", "pending"}:
        return "warning"

    return ""


def _mermaid_id(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_]", "_", text)

    if not text:
        text = "node"

    if not re.match(r"^[A-Za-z_]", text):
        text = f"n_{text}"

    return text


def _mermaid_label(value: Any) -> str:
    return (
        str(value)
        .replace('"', "'")
        .replace("\n", " ")
    )