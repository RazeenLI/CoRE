#!/usr/bin/env python3

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

"""
python data/visualize_rdb.py data/Chinook/parsed

python data/visualize_rdb.py data/Chinook/benchmarks/small_case_A_remove_columns/existing
python data/visualize_rdb.py save/example

python data/visualize_rdb.py data/Chinook/benchmarks/small_pipeline_ABC/existing
python data/visualize_rdb.py data/Chinook/benchmarks/small_pipeline_ABC/expected
python data/visualize_rdb.py data/Chinook/benchmarks/small_case_C_remove_relationship_table/expected
"""
# -----------------------------
# IO
# -----------------------------

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return 0

    return max(0, len(rows) - 1)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# -----------------------------
# Name formatting
# -----------------------------

def mermaid_entity_name(name: str) -> str:
    """
    Mermaid ER entity names are safest as uppercase alphanumeric/underscore.
    """
    x = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if re.match(r"^[0-9]", x):
        x = "T_" + x
    return x.upper()


def mermaid_attr_name(name: str) -> str:
    x = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if re.match(r"^[0-9]", x):
        x = "c_" + x
    return x


def mermaid_type(type_name: str) -> str:
    x = re.sub(r"[^A-Za-z0-9_]", "_", type_name)
    if not x:
        x = "unknown"
    return x


def markdown_escape(x: Any) -> str:
    return str(x).replace("|", "\\|")


# -----------------------------
# Constraint helpers
# -----------------------------

def is_compact_constraints(constraints: Dict[str, Any]) -> bool:
    """
    Compact format:
      constraints.primary_keys: dict[table, list[column]]
      constraints.foreign_keys: dict[table, list[fk]]
    """
    c = constraints.get("constraints", {})
    return isinstance(c.get("primary_keys", {}), dict)


def get_primary_key_map(constraints: Dict[str, Any]) -> Dict[str, Set[str]]:
    pk_map: Dict[str, Set[str]] = {}
    primary_keys = constraints.get("constraints", {}).get("primary_keys", {})

    for table, columns in primary_keys.items():
        pk_map.setdefault(table, set()).update(columns)
    return pk_map

def get_foreign_key_column_map(constraints: Dict[str, Any]) -> Dict[str, Set[str]]:
    fk_col_map: Dict[str, Set[str]] = {}
    foreign_keys = constraints.get("constraints", {}).get("foreign_keys", {})

    for table, fks in foreign_keys.items():
        for fk in fks:
            fk_col_map.setdefault(table, set()).update(fk.get("columns", []))
    return fk_col_map


def get_foreign_keys(constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return normalized foreign keys as list[dict].

    Normalized output:
      [
        {
          "table": "invoice",
          "columns": ["customer_id"],
          "referenced_table": "customer",
          "referenced_columns": ["customer_id"]
        }
      ]

    This keeps the rest of visualize_rdb.py unchanged.
    """
    foreign_keys = constraints.get("constraints", {}).get("foreign_keys", {})

    out: List[Dict[str, Any]] = []

    for table, fks in foreign_keys.items():
        for fk in fks:
            normalized_fk = dict(fk)
            normalized_fk["table"] = table
            out.append(normalized_fk)

    return out


# -----------------------------
# Mermaid ER generation
# -----------------------------

def make_mermaid_er(
    schema: Dict[str, Any],
    constraints: Dict[str, Any],
    row_counts: Dict[str, int],
) -> str:
    pk_map = get_primary_key_map(constraints)
    fk_col_map = get_foreign_key_column_map(constraints)
    foreign_keys = get_foreign_keys(constraints)

    lines: List[str] = ["erDiagram"]

    for table, table_info in schema.get("tables", {}).items():
        entity = mermaid_entity_name(table)
        rows = row_counts.get(table, 0)

        lines.append(f"    {entity} {{")

        column_order = table_info.get("column_order", list(table_info.get("columns", {}).keys()))

        for col in column_order:
            col_info = table_info["columns"][col]
            raw_type = col_info.get("type", col_info.get("type_raw", "unknown"))

            col_type = mermaid_type(raw_type)
            col_name = mermaid_attr_name(col)

            tags = []
            if col in pk_map.get(table, set()):
                tags.append("PK")
            if col in fk_col_map.get(table, set()):
                tags.append("FK")

            tag_text = f" {','.join(tags)}" if tags else ""
            nullable = "nullable" if col_info.get("nullable", True) else "not_null"

            lines.append(f"        {col_type} {col_name}{tag_text} \"{nullable}\"")

        lines.append(f"    }}")

    lines.append("")

    for fk in foreign_keys:
        child_table = fk["table"]
        parent_table = fk["referenced_table"]

        if child_table not in schema["tables"]:
            continue
        if parent_table not in schema["tables"]:
            continue

        parent = mermaid_entity_name(parent_table)
        child = mermaid_entity_name(child_table)

        child_cols = ",".join(fk.get("columns", []))
        parent_cols = ",".join(fk.get("referenced_columns", []))
        label = f"{child_cols} -> {parent_cols}"

        # Generic FK relation:
        # one parent row can reference many child rows.
        lines.append(f"    {parent} ||--o{{ {child} : \"{label}\"")

    lines.append("")
    return "\n".join(lines)


def make_html(mermaid_code: str, title: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{
      startOnLoad: true,
      theme: "default",
      er: {{
        useMaxWidth: true
      }}
    }});
  </script>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
    }}
    .mermaid {{
      border: 1px solid #ddd;
      padding: 16px;
      border-radius: 8px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="mermaid">
{mermaid_code}
  </div>
</body>
</html>
"""

def make_md(mermaid_code: str, title: str) -> str:
    return f"""# {title}
```mermaid
{mermaid_code}
```
"""


# -----------------------------
# Referential dependency report
# -----------------------------

def make_dependency_json(
    schema: Dict[str, Any],
    constraints: Dict[str, Any],
    row_counts: Dict[str, int],
) -> Dict[str, Any]:
    pk_map = get_primary_key_map(constraints)
    foreign_keys = get_foreign_keys(constraints)

    tables = []

    for table, table_info in schema.get("tables", {}).items():
        column_order = table_info.get("column_order", list(table_info.get("columns", {}).keys()))

        tables.append({
            "table": table,
            "rows": row_counts.get(table, 0),
            "columns": column_order,
            "primary_key": list(pk_map.get(table, [])),
        })

    dependencies = []

    for fk in foreign_keys:
        child = fk["table"]
        parent = fk["referenced_table"]

        if child not in schema["tables"]:
            continue
        if parent not in schema["tables"]:
            continue

        dependencies.append({
            "from_table": child,
            "from_columns": fk.get("columns", []),
            "to_table": parent,
            "to_columns": fk.get("referenced_columns", []),
            "name": fk.get("name"),
            "on_delete": fk.get("on_delete"),
            "on_update": fk.get("on_update"),
        })

    return {
        "database": schema.get("database"),
        "dialect": schema.get("dialect"),
        "tables": tables,
        "referential_dependencies": dependencies,
    }


def make_dependency_markdown(dep_json: Dict[str, Any]) -> str:
    lines = []

    lines.append(f"# Referential Dependencies")
    lines.append("")
    lines.append(f"- database: `{dep_json.get('database')}`")
    lines.append(f"- dialect: `{dep_json.get('dialect')}`")
    lines.append("")

    lines.append("## Tables")
    lines.append("")
    lines.append("| table | rows | columns | primary_key |")
    lines.append("|---|---:|---|---|")

    for table in dep_json["tables"]:
        lines.append(
            "| {table} | {rows} | {columns} | {pk} |".format(
                table=markdown_escape(table["table"]),
                rows=table["rows"],
                columns=markdown_escape(", ".join(table["columns"])),
                pk=markdown_escape(", ".join(table["primary_key"])),
            )
        )

    lines.append("")
    lines.append("## Foreign Keys")
    lines.append("")

    if not dep_json["referential_dependencies"]:
        lines.append("No foreign keys found.")
        lines.append("")
        return "\n".join(lines)

    lines.append("| child_table | child_columns | parent_table | parent_columns | on_delete | on_update |")
    lines.append("|---|---|---|---|---|---|")

    for fk in dep_json["referential_dependencies"]:
        lines.append(
            "| {child} | {child_cols} | {parent} | {parent_cols} | {on_delete} | {on_update} |".format(
                child=markdown_escape(fk["from_table"]),
                child_cols=markdown_escape(", ".join(fk["from_columns"])),
                parent=markdown_escape(fk["to_table"]),
                parent_cols=markdown_escape(", ".join(fk["to_columns"])),
                on_delete=markdown_escape(fk.get("on_delete")),
                on_update=markdown_escape(fk.get("on_update")),
            )
        )

    lines.append("")
    return "\n".join(lines)


# -----------------------------
# Main
# -----------------------------

def visualize_rdb(rdb_dir: Path) -> None:
    schema_path = rdb_dir / "schema.json"
    constraints_path = rdb_dir / "constraints.json"
    tables_dir = rdb_dir / "tables"

    schema = read_json(schema_path)
    constraints = read_json(constraints_path)

    row_counts = {}
    for table in schema.get("tables", {}):
        row_counts[table] = count_csv_rows(tables_dir / f"{table}.csv")

    viz_dir = rdb_dir / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    mermaid_code = make_mermaid_er(schema, constraints, row_counts)
    dep_json = make_dependency_json(schema, constraints, row_counts)
    dep_md = make_dependency_markdown(dep_json)

    write_text(viz_dir / "er_diagram.md", make_md(mermaid_code, title=f"ER Diagram: {rdb_dir.name}"))
    write_text(viz_dir / "er_diagram.html", make_html(mermaid_code, title=f"ER Diagram: {rdb_dir.name}"))
    write_json(viz_dir / "referential_dependencies.json", dep_json)
    write_text(viz_dir / "referential_dependencies.md", dep_md)

    print(f"Generated:")
    print(f"  {viz_dir / 'er_diagram.md'}")
    print(f"  {viz_dir / 'er_diagram.html'}")
    print(f"  {viz_dir / 'referential_dependencies.md'}")
    print(f"  {viz_dir / 'referential_dependencies.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize schema.json + constraints.json + tables/*.csv as ER diagram and FK report."
    )
    parser.add_argument(
        "rdb_dir",
        type=Path,
        help="Path to RDB directory containing schema.json, constraints.json, and tables/"
    )

    args = parser.parse_args()
    visualize_rdb(args.rdb_dir)


if __name__ == "__main__":
    main()