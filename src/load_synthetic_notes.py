#!/usr/bin/env python3
"""
Load synthetic notes into the pipeline for testing.

Copies data/synthetic/notes_synthetic.jsonl → data/processed/notes_clean.jsonl
so the downstream steps (extract_fields.py, build_import_csv.py) can run
without needing Epic access.

Usage:
    python src/load_synthetic_notes.py
    python src/extract_fields.py
    python src/build_import_csv.py
"""
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()

    src = Path("./data/synthetic/notes_synthetic.jsonl")
    dst = Path(os.getenv("CLEAN_NOTES_JSONL", "./data/processed/notes_clean.jsonl"))

    if not src.exists():
        raise FileNotFoundError(f"Synthetic notes not found at {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    # Count records
    count = sum(1 for line in dst.open() if line.strip())
    print(f"Loaded {count} synthetic notes → {dst}")
    print("\nNow run the downstream steps:")
    print("  python src/extract_fields.py")
    print("  python src/build_import_csv.py")


if __name__ == "__main__":
    main()
