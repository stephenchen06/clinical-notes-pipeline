#!/usr/bin/env python3
"""Run the full evaluation pipeline on synthetic notes."""
import subprocess
import sys

steps = [
    ("Extracting fields", "src/extract_fields.py"),
    ("Building import CSV", "src/build_import_csv.py"),
    ("Evaluating accuracy", "src/evaluate_extraction.py"),
    ("Generating accuracy chart", "src/visualize_accuracy.py"),
]

for label, script in steps:
    print(f"\n{'='*60}")
    print(f"  {label}...")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"\n[error] {script} failed — stopping.")
        sys.exit(result.returncode)

print("\nDone.")
