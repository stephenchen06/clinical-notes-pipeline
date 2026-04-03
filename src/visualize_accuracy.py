#!/usr/bin/env python3
"""
Generate a presentation-ready accuracy chart comparing model output
against ground truth for each REDCap field.

Usage:
    python src/visualize_accuracy.py

Output:
    data/reports/redcap_accuracy.png
"""
import csv
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from dotenv import load_dotenv

META_COLS = {"record_id", "patient_id", "document_reference_id", "note_date", "title"}

# Human-readable labels and category groupings for each base field
FIELD_META = {
    # Medical History
    "hand_dom":                ("Handedness",                     "Medical History"),
    "sz_age":                  ("Age at Seizure Onset",           "Medical History"),
    "medhx_etio":              ("Seizure Type Classification",    "Medical History"),
    "medhx_etio_focal":        ("Seizure Etiology",               "Medical History"),
    "medhx_szsyndrome":        ("Epilepsy Syndrome (Y/N)",        "Medical History"),
    "medhx_szsyndrome_type":   ("Epilepsy Syndrome Type",         "Medical History"),
    "medhx_prior_episgy":      ("Prior Epilepsy Surgery (Y/N)",   "Medical History"),
    "medhx_priorepisgy_type":  ("Prior Surgery Type",             "Medical History"),
    "medhx_neurohx":           ("Neurological Comorbidities",     "Medical History"),
    "medhx_psych":             ("Psychiatric Comorbidities",      "Medical History"),
    "medhx_si":                ("Suicidal Ideation History",      "Medical History"),
    "medhx_driving":           ("Currently Driving",              "Medical History"),
    "medhx_sgy_cand_yn":       ("Surgical Candidate",             "Medical History"),
    # Seizure
    "emu_sz_type":             ("Primary Seizure Type",           "Seizure"),
    "emu_sz_type1_freq":       ("Seizure Frequency",              "Seizure"),
    # ASMs
    "emu_asm_number":          ("# ASMs on Admission",            "Medications"),
    "emu_asm_type":            ("ASMs on Admission",              "Medications"),
    "emu_asm_sfx":             ("ASM Side Effects",               "Medications"),
    "emu_asmdc_number":        ("# ASMs on Discharge",            "Medications"),
    "emu_asmdc_type":          ("ASMs on Discharge",              "Medications"),
    # Discharge / EMU
    "emu_dcevents_type":       ("Discharge Diagnosis",            "EMU Discharge"),
    "emu_epilepsytype":        ("Epilepsy Type/Localization",     "EMU Discharge"),
    "emu_epilepsy_intract":    ("Medically Refractory",           "EMU Discharge"),
    "emu_sxcandidate":         ("Surgical Candidacy Status",      "EMU Discharge"),
    # Imaging
    "mri_yn":                  ("MRI Performed",                  "Imaging"),
    "mri_normal_abnormal":     ("MRI Normal/Abnormal",            "Imaging"),
    "mri_lateralization":      ("MRI Lateralization",             "Imaging"),
    "mri_l_localization":      ("MRI Localization (Left)",        "Imaging"),
    "mri_r_localization":      ("MRI Localization (Right)",       "Imaging"),
    "mri_lesion_left":         ("MRI Lesion Type (Left)",         "Imaging"),
    "mri_lesion_right":        ("MRI Lesion Type (Right)",        "Imaging"),
    "pet_yn":                  ("FDG-PET Performed",              "Imaging"),
    "fmri_yn":                 ("fMRI Performed",                 "Imaging"),
    "wada_yn":                 ("WADA Performed",                 "Imaging"),
}

CATEGORY_COLORS = {
    "Medical History": "#4C72B0",
    "Seizure":         "#DD8452",
    "Medications":     "#55A868",
    "EMU Discharge":   "#C44E52",
    "Imaging":         "#8172B2",
}


def load_csv(path: Path) -> dict:
    rows = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doc_id = row.get("document_reference_id", "")
            if doc_id:
                rows[doc_id] = row
    return rows


def group_column_to_field(col: str) -> str:
    return col.split("___")[0] if "___" in col else col


def compute_field_accuracy(expected: dict, actual: dict) -> dict:
    """Returns {base_field: (correct, total)} across all common patients."""
    common_ids = set(expected) & set(actual)
    sample = next(iter(expected.values()))
    columns = [c for c in sample if c not in META_COLS]

    per_field = defaultdict(lambda: [0, 0])  # [correct, total]
    for doc_id in common_ids:
        for col in columns:
            base = group_column_to_field(col)
            exp = expected[doc_id].get(col, "").strip()
            act = actual[doc_id].get(col, "").strip()
            per_field[base][1] += 1
            if exp == act:
                per_field[base][0] += 1

    return {f: (c, t) for f, (c, t) in per_field.items()}


def main():
    load_dotenv()

    expected_path = Path("./data/synthetic/redcap_expected.csv")
    actual_path = Path(os.getenv("REDCAP_CSV", "./data/processed/redcap_import.csv"))
    out_path = Path("./data/reports/redcap_accuracy.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not expected_path.exists():
        print(f"Ground truth not found: {expected_path}")
        print("Run: python src/generate_expected_csv.py")
        return
    if not actual_path.exists():
        print(f"Model output not found: {actual_path}")
        print("Run the pipeline first.")
        return

    expected = load_csv(expected_path)
    actual = load_csv(actual_path)
    field_acc = compute_field_accuracy(expected, actual)

    # Build ordered list: group by category, sort by accuracy within each group
    category_order = ["Medical History", "Seizure", "Medications", "EMU Discharge", "Imaging"]
    grouped = defaultdict(list)
    for field, (c, t) in field_acc.items():
        label, category = FIELD_META.get(field, (field, "Other"))
        grouped[category].append((label, c / t * 100, CATEGORY_COLORS.get(category, "#999")))

    for cat in grouped:
        grouped[cat].sort(key=lambda x: x[1])  # sort by accuracy within category

    # Flatten in category order
    labels, values, colors = [], [], []
    category_boundaries = {}
    idx = 0
    for cat in category_order:
        if cat not in grouped:
            continue
        for label, pct, color in grouped[cat]:
            labels.append(label)
            values.append(pct)
            colors.append(color)
        category_boundaries[cat] = (idx, idx + len(grouped[cat]) - 1)
        idx += len(grouped[cat])

    # -----------------------------------------------------------------------
    # Plot
    # -----------------------------------------------------------------------
    n = len(labels)
    fig_height = max(8, n * 0.38)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    fig.patch.set_facecolor("#F8F9FA")
    ax.set_facecolor("#F8F9FA")

    y_pos = range(n)
    bars = ax.barh(y_pos, values, color=colors, height=0.65, zorder=3)

    # Value labels on bars
    for bar, val in zip(bars, values):
        x = bar.get_width()
        label_x = x + 1 if x < 95 else x - 3
        ha = "left" if x < 95 else "right"
        color = "#333333" if x < 95 else "white"
        ax.text(label_x, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", ha=ha,
                fontsize=9, fontweight="bold", color=color)

    # Field labels
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(0, 108)
    ax.set_xlabel("Accuracy (%)", fontsize=11, labelpad=10)

    # Reference lines
    for x in [25, 50, 75, 100]:
        ax.axvline(x, color="#CCCCCC", linewidth=0.8, linestyle="--", zorder=1)

    # Category dividers
    for cat, (start, end) in category_boundaries.items():
        mid = (start + end) / 2
        ax.text(106, mid, cat, va="center", ha="right",
                fontsize=8.5, color=CATEGORY_COLORS.get(cat, "#999"),
                fontweight="bold", style="italic")
        if start > 0:
            ax.axhline(start - 0.5, color="#DDDDDD", linewidth=1.2, zorder=2)

    # Overall accuracy
    overall = sum(values) / len(values) if values else 0
    ax.axvline(overall, color="#E63946", linewidth=1.8, linestyle="-", zorder=4,
               label=f"Overall avg: {overall:.1f}%")

    # Legend
    legend_handles = [
        mpatches.Patch(color=CATEGORY_COLORS[cat], label=cat)
        for cat in category_order if cat in grouped
    ]
    legend_handles.append(
        plt.Line2D([0], [0], color="#E63946", linewidth=2, label=f"Avg: {overall:.1f}%")
    )
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9,
              framealpha=0.9, edgecolor="#CCCCCC")

    n_patients = len(set(expected) & set(actual))
    ax.set_title(
        f"REDCap Field Extraction Accuracy\n"
        f"Model: {os.getenv('OLLAMA_MODEL', 'llama3.2:11b')}  |  "
        f"n = {n_patients} synthetic EMU notes",
        fontsize=13, fontweight="bold", pad=16
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.grid(axis="x", color="#EEEEEE", zorder=0)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved chart → {out_path}")
    print(f"Overall average accuracy: {overall:.1f}%")


if __name__ == "__main__":
    main()
