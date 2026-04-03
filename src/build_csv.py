#!/usr/bin/env python3
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv


def to_pipe_list(value):
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    return str(value) if value is not None else ""


def main():
    load_dotenv()

    in_path = Path(os.getenv("SUMMARIES_JSONL", "./data/processed/notes_summaries.jsonl"))
    out_path = Path(os.getenv("OUTPUT_CSV", "./data/processed/notes_summary.csv"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise FileNotFoundError(f"Summaries file not found: {in_path}")

    fieldnames = [
        "patient_id",
        "document_reference_id",
        "note_date",
        "title",
        "summary",
        "chief_complaint",
        "key_diagnoses",
        "medications",
        "follow_up",
        "red_flags",
    ]

    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for line in fin:
            row = json.loads(line)
            writer.writerow(
                {
                    "patient_id": row.get("patient_id", ""),
                    "document_reference_id": row.get("document_reference_id", ""),
                    "note_date": row.get("note_date", ""),
                    "title": row.get("title", ""),
                    "summary": row.get("summary", ""),
                    "chief_complaint": row.get("chief_complaint", ""),
                    "key_diagnoses": to_pipe_list(row.get("key_diagnoses", [])),
                    "medications": to_pipe_list(row.get("medications", [])),
                    "follow_up": row.get("follow_up", ""),
                    "red_flags": to_pipe_list(row.get("red_flags", [])),
                }
            )
            count += 1

    print(f"Wrote {count} rows to {out_path}")


if __name__ == "__main__":
    main()
