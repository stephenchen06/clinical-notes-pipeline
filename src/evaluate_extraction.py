#!/usr/bin/env python3
"""
Evaluate REDCap extraction accuracy against ground truth.

Compares data/processed/redcap_import.csv (model output)
against data/synthetic/redcap_expected.csv (ground truth).

Usage:
    python src/evaluate_extraction.py

Output:
    - Per-field accuracy across all patients
    - Per-patient accuracy
    - Overall accuracy
    - Detailed diff for any mismatches
"""
import csv
import os
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv

# Metadata columns — excluded from accuracy scoring
META_COLS = {"record_id", "patient_id", "document_reference_id", "note_date", "title"}


def load_csv(path: Path) -> dict[str, dict]:
    """Load CSV keyed by document_reference_id."""
    rows = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doc_id = row.get("document_reference_id", "")
            if doc_id:
                rows[doc_id] = row
    return rows


def get_redcap_columns(row: dict) -> list[str]:
    return [col for col in row if col not in META_COLS]


def compare_rows(expected: dict, actual: dict, columns: list[str]) -> dict:
    """Return per-column match results for one patient."""
    results = {}
    for col in columns:
        exp_val = expected.get(col, "").strip()
        act_val = actual.get(col, "").strip()
        results[col] = {
            "match": exp_val == act_val,
            "expected": exp_val,
            "actual": act_val,
        }
    return results


def group_column_to_field(col: str) -> str:
    """Map checkbox column (field___code) back to the base field name."""
    if "___" in col:
        return col.split("___")[0]
    return col


def main():
    load_dotenv()

    expected_path = Path("./data/synthetic/redcap_expected.csv")
    actual_path = Path(os.getenv("REDCAP_CSV", "./data/processed/redcap_import.csv"))

    if not expected_path.exists():
        print(f"Ground truth not found: {expected_path}")
        print("Run: python src/generate_expected_csv.py")
        return

    if not actual_path.exists():
        print(f"Model output not found: {actual_path}")
        print("Run the pipeline first: python src/extract_fields.py && python src/build_import_csv.py")
        return

    expected = load_csv(expected_path)
    actual = load_csv(actual_path)

    # Determine columns from expected CSV
    sample_row = next(iter(expected.values()))
    columns = get_redcap_columns(sample_row)

    common_ids = sorted(set(expected) & set(actual))
    only_expected = set(expected) - set(actual)
    only_actual = set(actual) - set(expected)

    if only_expected:
        print(f"[warn] In expected but not in model output: {only_expected}")
    if only_actual:
        print(f"[warn] In model output but not in expected: {only_actual}")

    if not common_ids:
        print("No matching document_reference_ids found between the two files.")
        return

    # -----------------------------------------------------------------------
    # Collect results
    # -----------------------------------------------------------------------
    # per_field[field_name] = [True/False, ...] one per patient
    per_field = defaultdict(list)
    # per_patient[doc_id] = (correct, total)
    per_patient = {}
    # mismatches for detailed output
    mismatches = defaultdict(list)

    for doc_id in common_ids:
        results = compare_rows(expected[doc_id], actual[doc_id], columns)
        correct = sum(1 for r in results.values() if r["match"])
        per_patient[doc_id] = (correct, len(columns))

        for col, r in results.items():
            base_field = group_column_to_field(col)
            per_field[base_field].append(r["match"])
            if not r["match"]:
                mismatches[doc_id].append({
                    "column": col,
                    "expected": r["expected"],
                    "actual": r["actual"],
                })

    # -----------------------------------------------------------------------
    # Print report
    # -----------------------------------------------------------------------
    total_correct = sum(c for c, _ in per_patient.values())
    total_fields = sum(t for _, t in per_patient.values())
    overall_pct = 100 * total_correct / total_fields if total_fields else 0

    print("=" * 65)
    print("  REDCap Extraction Accuracy Report")
    print("=" * 65)
    print(f"  Patients evaluated : {len(common_ids)}")
    print(f"  Columns per patient: {len(columns)}")
    print(f"  Overall accuracy   : {total_correct}/{total_fields} ({overall_pct:.1f}%)")
    print()

    # Per-field accuracy (grouped by base field, sorted by accuracy)
    print("── Field-level accuracy ─────────────────────────────────────")
    field_acc = {}
    for field, matches in per_field.items():
        n = len(matches)
        c = sum(matches)
        field_acc[field] = (c, n)

    # Sort by accuracy ascending so worst fields show first
    for field, (c, n) in sorted(field_acc.items(), key=lambda x: x[1][0] / x[1][1]):
        pct = 100 * c / n
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"  {field:<35} {bar}  {c}/{n} ({pct:.0f}%)")

    print()
    print("── Per-patient accuracy ──────────────────────────────────────")
    for doc_id in common_ids:
        c, t = per_patient[doc_id]
        pct = 100 * c / t
        title = expected[doc_id].get("title", doc_id)[:45]
        print(f"  {doc_id}  {pct:5.1f}%  {c}/{t}  {title}")

    # Detailed mismatches
    if any(mismatches.values()):
        print()
        print("── Mismatches (expected → actual) ────────────────────────────")
        for doc_id in common_ids:
            if not mismatches[doc_id]:
                continue
            title = expected[doc_id].get("title", doc_id)
            print(f"\n  [{doc_id}] {title}")
            for m in mismatches[doc_id]:
                print(f"    {m['column']:<45} expected={m['expected']!r:>4}  actual={m['actual']!r}")

    print()
    print("=" * 65)


if __name__ == "__main__":
    main()
