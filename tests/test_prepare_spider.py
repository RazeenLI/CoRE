from __future__ import annotations

import csv
import json
import sqlite3

from data.prepare_spider import write_parsed_database


def test_write_parsed_database_extracts_schema_constraints_and_rows(tmp_path):
    sqlite_path = tmp_path / "shop.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE Customer (
            CustomerId INTEGER PRIMARY KEY,
            Name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE Invoice (
            InvoiceId INTEGER PRIMARY KEY,
            CustomerId INTEGER NOT NULL,
            Total NUMERIC(10,2),
            FOREIGN KEY (CustomerId) REFERENCES Customer(CustomerId)
        );
        INSERT INTO Customer VALUES (1, 'Ada');
        INSERT INTO Invoice VALUES (10, 1, 12.5);
        """
    )
    connection.commit()
    connection.close()

    output_dir = tmp_path / "parsed" / "shop"
    summary = write_parsed_database(sqlite_path, output_dir)

    schema = json.loads((output_dir / "schema.json").read_text())
    constraints = json.loads((output_dir / "constraints.json").read_text())
    with (output_dir / "tables" / "invoice.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))

    assert summary["table_count"] == 2
    assert summary["row_count"] == 2
    assert list(schema["tables"]) == ["customer", "invoice"]
    assert schema["tables"]["invoice"]["columns"]["total"]["type"] == "decimal"
    assert constraints["constraints"]["primary_keys"]["customer"] == ["customerid"]
    assert constraints["constraints"]["foreign_keys"]["invoice"] == [
        {
            "columns": ["customerid"],
            "referenced_table": "customer",
            "referenced_columns": ["customerid"],
        }
    ]
    assert rows == [{"invoiceid": "10", "customerid": "1", "total": "12.5"}]


def test_write_parsed_database_repairs_non_utf8_text(tmp_path):
    sqlite_path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(sqlite_path)
    connection.execute("CREATE TABLE Person (PersonId INTEGER PRIMARY KEY, LastName TEXT)")
    connection.execute("INSERT INTO Person VALUES (1, CAST(X'5065F161' AS TEXT))")
    connection.commit()
    connection.close()

    output_dir = tmp_path / "parsed" / "legacy"
    summary = write_parsed_database(sqlite_path, output_dir)

    with (output_dir / "tables" / "person.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["lastname"] == "Peña"
    assert summary["warnings"] == [
        {
            "kind": "non_utf8_text_repaired",
            "value_count": 1,
            "fallback_encodings": ["windows-1252"],
        }
    ]
