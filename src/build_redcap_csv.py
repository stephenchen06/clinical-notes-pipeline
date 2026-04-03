#!/usr/bin/env python3
"""
Convert notes_redcap.jsonl to a REDCap-importable CSV.

REDCap checkbox fields use a special column format:
  fieldname___choicecode = 1 (checked) or 0 (unchecked)

All other fields use the variable name directly as the column header.
The output CSV can be imported directly into REDCap via Data Import Tool.
"""
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from extract_redcap_fields import REDCAP_FIELDS, CHECKBOX_FIELDS


def build_fieldnames(redcap_fields_schema: dict) -> list[str]:
    """Build the ordered list of CSV column headers."""
    cols = ["record_id", "patient_id", "document_reference_id", "note_date", "title"]

    for var, meta in redcap_fields_schema.items():
        if meta["type"] == "checkbox":
            # REDCap checkbox columns: fieldname___code for every possible choice
            for code in meta["choices"]:
                cols.append(f"{var}___{code}")
        else:
            cols.append(var)

    return cols


def flatten_record(row: dict, fieldnames: list[str]) -> dict:
    """Convert a notes_redcap.jsonl record into a flat CSV row."""
    rf = row.get("redcap_fields", {})
    out = {
        "record_id": row.get("patient_id", ""),
        "patient_id": row.get("patient_id", ""),
        "document_reference_id": row.get("document_reference_id", ""),
        "note_date": row.get("note_date", ""),
        "title": row.get("title", ""),
    }

    for var, meta in REDCAP_FIELDS.items():
        if meta["type"] == "checkbox":
            checked_codes = set(rf.get(var) or [])
            for code in meta["choices"]:
                col = f"{var}___{code}"
                out[col] = "1" if code in checked_codes else "0"
        else:
            value = rf.get(var)
            out[var] = value if value is not None else ""

    return out


def main():
    load_dotenv()

    in_path = Path(os.getenv("REDCAP_JSONL", "./data/processed/notes_redcap.jsonl"))
    out_path = Path(os.getenv("REDCAP_CSV", "./data/processed/redcap_import.csv"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise FileNotFoundError(f"REDCap JSONL not found: {in_path}")

    fieldnames = build_fieldnames(REDCAP_FIELDS)

    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for line in fin:
            row = json.loads(line)
            flat = flatten_record(row, fieldnames)
            writer.writerow(flat)
            count += 1

    print(f"Wrote {count} rows to {out_path}")
    print(f"Columns: {len(fieldnames)} (including {len(fieldnames) - 5} REDCap fields)")


if __name__ == "__main__":
    main()
