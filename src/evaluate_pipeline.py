#!/usr/bin/env python3
"""Run the full evaluation pipeline on synthetic notes."""
import subprocess
import sys

steps = [
    ("Extracting REDCap fields", "src/extract_redcap_fields.py"),
    ("Building REDCap CSV", "src/build_redcap_csv.py"),
    ("Evaluating accuracy", "src/evaluate_redcap_extraction.py"),
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
