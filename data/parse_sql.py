#!/usr/bin/env python3

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

"""
python data/parse_sql.py \
  --input data/Chinook/raw/Chinook_PostgreSql.sql \
  --output data/Chinook/parsed
"""
# -----------------------------
# Basic SQL utilities
# -----------------------------

def clean_identifier(name: str) -> str:
    name = name.strip().rstrip(";")
    if "." in name:
        name = name.split(".")[-1]
    if name.startswith('"') and name.endswith('"'):
        return name[1:-1].replace('""', '"')
    return name.lower()


def make_id(prefix: str, *parts: str) -> str:
    raw = "_".join([prefix, *parts]).lower()
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")


def strip_sql_comments(sql: str) -> str:
    out = []
    i = 0
    quote: Optional[str] = None

    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue

        if ch == "-" and nxt == "-":
            while i < len(sql) and sql[i] != "\n":
                i += 1
            out.append("\n")
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(sql) and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def split_sql_statements(sql: str) -> List[str]:
    statements = []
    buf = []
    quote: Optional[str] = None
    i = 0

    while i < len(sql):
        ch = sql[i]

        if quote:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    return statements


def split_top_level_commas(text: str) -> List[str]:
    parts = []
    buf = []
    depth = 0
    quote: Optional[str] = None
    i = 0

    while i < len(text):
        ch = text[i]

        if quote:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue

        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    final = "".join(buf).strip()
    if final:
        parts.append(final)

    return parts


def parse_identifier_list(text: str) -> List[str]:
    return [clean_identifier(x) for x in split_top_level_commas(text)]


def first_top_level_keyword_pos(text: str, keywords: List[str]) -> Optional[int]:
    upper = text.upper()
    depth = 0
    quote: Optional[str] = None
    i = 0

    while i < len(text):
        ch = text[i]

        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue

        if ch == "(":
            depth += 1
            i += 1
            continue

        if ch == ")":
            depth -= 1
            i += 1
            continue

        if depth == 0:
            for kw in keywords:
                if upper.startswith(kw, i):
                    before_ok = i == 0 or not (upper[i - 1].isalnum() or upper[i - 1] == "_")
                    after = i + len(kw)
                    after_ok = after >= len(upper) or not (upper[after].isalnum() or upper[after] == "_")
                    if before_ok and after_ok:
                        return i

        i += 1

    return None


# -----------------------------
# Type parsing
# -----------------------------

def normalize_type(type_raw: str) -> Dict[str, Any]:
    s = re.sub(r"\s+", " ", type_raw.strip())
    lower = s.lower()

    out: Dict[str, Any] = {"type_raw": s}

    varchar_m = re.match(r"^(varchar|character varying|char|character)\s*\((\d+)\)$", lower)
    numeric_m = re.match(r"^(numeric|decimal)\s*\((\d+)\s*,\s*(\d+)\)$", lower)

    if varchar_m:
        out["type"] = "string"
        out["max_length"] = int(varchar_m.group(2))
    elif numeric_m:
        out["type"] = "decimal"
        out["precision"] = int(numeric_m.group(2))
        out["scale"] = int(numeric_m.group(3))
    elif lower in {"int", "integer", "serial"}:
        out["type"] = "integer"
    elif lower in {"bigint", "bigserial"}:
        out["type"] = "bigint"
    elif lower in {"smallint", "smallserial"}:
        out["type"] = "smallint"
    elif lower.startswith("timestamp"):
        out["type"] = "timestamp"
    elif lower == "date":
        out["type"] = "date"
    elif lower in {"bool", "boolean"}:
        out["type"] = "boolean"
    elif lower == "text":
        out["type"] = "text"
    elif lower in {"real", "double precision", "float", "float4", "float8"}:
        out["type"] = "float"
    else:
        out["type"] = lower

    return out


# -----------------------------
# Constraint helpers
# -----------------------------

def add_primary_key(constraints: Dict[str, Any], table: str, columns: List[str], name: Optional[str]) -> None:
    constraints["constraints"]["primary_keys"].append({
        "id": make_id("pk", table, "_".join(columns)),
        "table": table,
        "columns": columns,
        "name": clean_identifier(name) if name else None,
        "source": "ddl",
        "confidence": 1.0
    })


def add_unique_constraint(constraints: Dict[str, Any], table: str, columns: List[str], name: Optional[str]) -> None:
    constraints["constraints"]["unique_constraints"].append({
        "id": make_id("uq", table, "_".join(columns)),
        "table": table,
        "columns": columns,
        "name": clean_identifier(name) if name else None,
        "source": "ddl",
        "confidence": 1.0
    })


def add_check_constraint(constraints: Dict[str, Any], table: str, expression: str, name: Optional[str]) -> None:
    constraints["constraints"]["check_constraints"].append({
        "id": make_id("ck", table, name or str(len(constraints["constraints"]["check_constraints"]) + 1)),
        "table": table,
        "expression": expression.strip(),
        "name": clean_identifier(name) if name else None,
        "source": "ddl",
        "confidence": 1.0
    })


def parse_referential_action(rest: str, action: str) -> Optional[str]:
    m = re.search(
        rf"\bON\s+{action}\s+(NO\s+ACTION|CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT)\b",
        rest,
        flags=re.IGNORECASE
    )
    if not m:
        return None
    return re.sub(r"\s+", "_", m.group(1).strip().lower())


def add_foreign_key(
    constraints: Dict[str, Any],
    table: str,
    columns: List[str],
    referenced_table: str,
    referenced_columns: List[str],
    name: Optional[str],
    rest: str = ""
) -> None:
    constraints["constraints"]["foreign_keys"].append({
        "id": make_id("fk", table, "_".join(columns), referenced_table, "_".join(referenced_columns)),
        "table": table,
        "columns": columns,
        "referenced_table": referenced_table,
        "referenced_columns": referenced_columns,
        "name": clean_identifier(name) if name else None,
        "on_delete": parse_referential_action(rest, "DELETE"),
        "on_update": parse_referential_action(rest, "UPDATE"),
        "source": "ddl",
        "confidence": 1.0
    })


def parse_foreign_key_body(
    table: str,
    body: str,
    name: Optional[str],
    constraints: Dict[str, Any]
) -> bool:
    m = re.search(
        r"FOREIGN\s+KEY\s*\((?P<cols>.*?)\)\s+REFERENCES\s+(?P<ref_table>[^\s(]+)\s*\((?P<ref_cols>.*?)\)(?P<rest>.*)$",
        body,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return False

    add_foreign_key(
        constraints=constraints,
        table=table,
        columns=parse_identifier_list(m.group("cols")),
        referenced_table=clean_identifier(m.group("ref_table")),
        referenced_columns=parse_identifier_list(m.group("ref_cols")),
        name=name,
        rest=m.group("rest")
    )
    return True


# -----------------------------
# DDL parsers
# -----------------------------

def parse_create_table(stmt: str, schema: Dict[str, Any], constraints: Dict[str, Any]) -> None:
    m = re.match(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<table>[^\s(]+)\s*\((?P<body>.*)\)\s*$",
        stmt,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return

    table = clean_identifier(m.group("table"))
    body = m.group("body")

    schema["tables"].setdefault(table, {
        "columns": {},
        "column_order": []
    })

    for item in split_top_level_commas(body):
        item_clean = item.strip()
        constraint_name = None

        c_m = re.match(
            r"CONSTRAINT\s+([^\s]+)\s+(.*)$",
            item_clean,
            flags=re.IGNORECASE | re.DOTALL
        )
        if c_m:
            constraint_name = c_m.group(1)
            item_clean = c_m.group(2).strip()

        pk_m = re.match(r"PRIMARY\s+KEY\s*\((.*?)\)", item_clean, flags=re.IGNORECASE | re.DOTALL)
        if pk_m:
            cols = parse_identifier_list(pk_m.group(1))
            add_primary_key(constraints, table, cols, constraint_name)
            continue

        uq_m = re.match(r"UNIQUE\s*\((.*?)\)", item_clean, flags=re.IGNORECASE | re.DOTALL)
        if uq_m:
            add_unique_constraint(constraints, table, parse_identifier_list(uq_m.group(1)), constraint_name)
            continue

        ck_m = re.match(r"CHECK\s*\((.*)\)", item_clean, flags=re.IGNORECASE | re.DOTALL)
        if ck_m:
            add_check_constraint(constraints, table, ck_m.group(1), constraint_name)
            continue

        if item_clean.upper().startswith("FOREIGN KEY"):
            parse_foreign_key_body(table, item_clean, constraint_name, constraints)
            continue

        col_m = re.match(
            r'\s*("[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s+(?P<rest>.*)$',
            item,
            flags=re.DOTALL
        )
        if not col_m:
            continue

        col = clean_identifier(col_m.group(1))
        rest = col_m.group("rest").strip()

        attr_start = first_top_level_keyword_pos(
            rest,
            [
                "NOT NULL",
                "NULL",
                "DEFAULT",
                "PRIMARY KEY",
                "REFERENCES",
                "UNIQUE",
                "CHECK",
                "CONSTRAINT",
                "COLLATE"
            ]
        )

        type_raw = rest[:attr_start].strip() if attr_start is not None else rest
        attrs = rest[attr_start:].strip() if attr_start is not None else ""

        col_info = normalize_type(type_raw)
        col_info["nullable"] = not bool(re.search(r"\bNOT\s+NULL\b", attrs, flags=re.IGNORECASE))

        default_m = re.search(
            r"\bDEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|PRIMARY\s+KEY|REFERENCES|UNIQUE|CHECK|CONSTRAINT)\b|$)",
            attrs,
            flags=re.IGNORECASE | re.DOTALL
        )
        if default_m:
            col_info["default"] = default_m.group(1).strip()

        schema["tables"][table]["columns"][col] = col_info
        schema["tables"][table]["column_order"].append(col)

        if re.search(r"\bPRIMARY\s+KEY\b", attrs, flags=re.IGNORECASE):
            col_info["nullable"] = False
            add_primary_key(constraints, table, [col], constraint_name)

        if re.search(r"\bUNIQUE\b", attrs, flags=re.IGNORECASE):
            add_unique_constraint(constraints, table, [col], constraint_name)

        ref_m = re.search(
            r"\bREFERENCES\s+([^\s(]+)\s*\((.*?)\)",
            attrs,
            flags=re.IGNORECASE | re.DOTALL
        )
        if ref_m:
            add_foreign_key(
                constraints=constraints,
                table=table,
                columns=[col],
                referenced_table=clean_identifier(ref_m.group(1)),
                referenced_columns=parse_identifier_list(ref_m.group(2)),
                name=constraint_name,
                rest=attrs
            )


def parse_alter_table(stmt: str, constraints: Dict[str, Any]) -> None:
    m = re.match(
        r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[^\s]+)\s+ADD\s+CONSTRAINT\s+(?P<name>[^\s]+)\s+(?P<body>.*)$",
        stmt,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return

    table = clean_identifier(m.group("table"))
    name = m.group("name")
    body = m.group("body").strip()

    if body.upper().startswith("FOREIGN KEY"):
        parse_foreign_key_body(table, body, name, constraints)
        return

    pk_m = re.match(r"PRIMARY\s+KEY\s*\((.*?)\)", body, flags=re.IGNORECASE | re.DOTALL)
    if pk_m:
        add_primary_key(constraints, table, parse_identifier_list(pk_m.group(1)), name)
        return

    uq_m = re.match(r"UNIQUE\s*\((.*?)\)", body, flags=re.IGNORECASE | re.DOTALL)
    if uq_m:
        add_unique_constraint(constraints, table, parse_identifier_list(uq_m.group(1)), name)
        return

    ck_m = re.match(r"CHECK\s*\((.*)\)", body, flags=re.IGNORECASE | re.DOTALL)
    if ck_m:
        add_check_constraint(constraints, table, ck_m.group(1), name)


def parse_create_index(stmt: str, constraints: Dict[str, Any]) -> None:
    m = re.match(
        r"CREATE\s+(?P<unique>UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[^\s]+)\s+ON\s+(?P<table>[^\s(]+)\s*\((?P<cols>.*?)\)\s*$",
        stmt,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return

    table = clean_identifier(m.group("table"))
    cols = parse_identifier_list(m.group("cols"))
    name = clean_identifier(m.group("name"))
    unique = bool(m.group("unique"))

    constraints["constraints"]["indexes"].append({
        "id": make_id("idx", table, "_".join(cols)),
        "table": table,
        "columns": cols,
        "name": name,
        "unique": unique,
        "source": "ddl",
        "confidence": 1.0
    })

    if unique:
        add_unique_constraint(constraints, table, cols, name)


# -----------------------------
# INSERT parser
# -----------------------------

def parse_sql_literal(token: str) -> Any:
    t = token.strip()

    if not t:
        return ""

    if re.fullmatch(r"NULL", t, flags=re.IGNORECASE):
        return None

    if re.match(r"^[NnEe]?'", t):
        quote_pos = t.find("'")
        raw = t[quote_pos + 1:]
        if raw.endswith("'"):
            raw = raw[:-1]
        return raw.replace("''", "'")

    if t.startswith("'") and t.endswith("'"):
        return t[1:-1].replace("''", "'")

    return t


def parse_insert_values(values: str) -> List[List[Any]]:
    rows = []
    i = 0

    while i < len(values):
        while i < len(values) and values[i] in " \t\r\n,":
            i += 1

        if i >= len(values):
            break

        if values[i] != "(":
            break

        start = i + 1
        depth = 1
        quote: Optional[str] = None
        i += 1

        while i < len(values) and depth > 0:
            ch = values[i]

            if quote:
                if ch == quote:
                    if i + 1 < len(values) and values[i + 1] == quote:
                        i += 2
                        continue
                    quote = None
                i += 1
                continue

            if ch in ("'", '"'):
                quote = ch
                i += 1
                continue

            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

            i += 1

        row_text = values[start:i - 1]
        rows.append([parse_sql_literal(x) for x in split_top_level_commas(row_text)])

    return rows


def parse_insert(stmt: str, table_rows: Dict[str, List[Dict[str, Any]]]) -> None:
    m = re.match(
        r"INSERT\s+INTO\s+(?P<table>[^\s(]+)\s*\((?P<cols>.*?)\)\s+VALUES\s*(?P<values>.*)$",
        stmt,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return

    table = clean_identifier(m.group("table"))
    cols = parse_identifier_list(m.group("cols"))
    rows = parse_insert_values(m.group("values").strip())

    table_rows.setdefault(table, [])

    for row in rows:
        table_rows[table].append(dict(zip(cols, row)))


def parse_database_name(stmt: str) -> Optional[str]:
    m = re.match(r"CREATE\s+DATABASE\s+([^\s]+)", stmt, flags=re.IGNORECASE)
    if not m:
        return None
    return clean_identifier(m.group(1))


# -----------------------------
# Main parse pipeline
# -----------------------------

def parse_postgres_sql(
    sql: str,
    fallback_database_name: str
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:

    schema: Dict[str, Any] = {
        "database": fallback_database_name,
        # "dialect": "postgresql",
        # "version": "v1",
        "tables": {}
    }

    constraints: Dict[str, Any] = {
        "database": fallback_database_name,
        # "dialect": "postgresql",
        # "version": "v1",
        "constraints": {
            "primary_keys": [],
            "foreign_keys": [],
            "unique_constraints": [],
            "check_constraints": [],
            "indexes": [],
            "inferred_constraints": []
        }
    }

    table_rows: Dict[str, List[Dict[str, Any]]] = {}

    cleaned_sql = strip_sql_comments(sql)

    for stmt in split_sql_statements(cleaned_sql):
        stmt = stmt.strip()

        if not stmt or stmt.startswith("\\"):
            continue

        db_name = parse_database_name(stmt)
        if db_name:
            schema["database"] = db_name
            constraints["database"] = db_name
            continue

        upper = stmt.upper()

        if upper.startswith("CREATE TABLE"):
            parse_create_table(stmt, schema, constraints)
        elif upper.startswith("ALTER TABLE"):
            parse_alter_table(stmt, constraints)
        elif upper.startswith("CREATE INDEX") or upper.startswith("CREATE UNIQUE INDEX"):
            parse_create_index(stmt, constraints)
        elif upper.startswith("INSERT INTO"):
            parse_insert(stmt, table_rows)

    # Primary key columns are always non-null.
    for pk in constraints["constraints"]["primary_keys"]:
        table = pk["table"]
        for col in pk["columns"]:
            if table in schema["tables"] and col in schema["tables"][table]["columns"]:
                schema["tables"][table]["columns"][col]["nullable"] = False

    return schema, constraints, table_rows


# -----------------------------
# Output
# -----------------------------

def choose_csv_columns(table: str, schema: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[str]:
    if table in schema["tables"]:
        return list(schema["tables"][table].get("column_order", []))

    columns = []
    seen = set()

    for row in rows:
        for col in row:
            if col not in seen:
                columns.append(col)
                seen.add(col)

    return columns


def write_outputs(
    schema: Dict[str, Any],
    constraints: Dict[str, Any],
    table_rows: Dict[str, List[Dict[str, Any]]],
    output_dir: Path
) -> None:

    output_dir.mkdir(parents=True, exist_ok=True)

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "schema.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    (output_dir / "constraints.json").write_text(
        json.dumps(constraints, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    for table, rows in sorted(table_rows.items()):
        columns = choose_csv_columns(table, schema, rows)
        csv_path = tables_dir / f"{table}.csv"

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()

            for row in rows:
                writer.writerow({
                    col: "" if row.get(col) is None else row.get(col, "")
                    for col in columns
                })


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse PostgreSQL SQL into schema.json, constraints.json, and per-table CSV files."
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Input PostgreSQL .sql file"
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Output parsed directory"
    )

    args = parser.parse_args()

    sql = args.input.read_text(encoding="utf-8")
    fallback_db = args.input.stem.lower()

    schema, constraints, table_rows = parse_postgres_sql(sql, fallback_db)
    write_outputs(schema, constraints, table_rows, args.output)

    print(f"schema:      {args.output / 'schema.json'}")
    print(f"constraints: {args.output / 'constraints.json'}")
    print(f"tables:      {args.output / 'tables'}")
    print(f"table_count: {len(schema['tables'])}")
    print(f"row_count:   {sum(len(v) for v in table_rows.values())}")


if __name__ == "__main__":
    main()