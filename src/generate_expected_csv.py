#!/usr/bin/env python3
"""
Generate the ground truth REDCap CSV for the 8 synthetic notes.

Values here were manually determined by the note author and represent
the correct REDCap-coded answers for each synthetic patient.
Run this once to produce data/synthetic/redcap_expected.csv, which is
used by evaluate_extraction.py to measure model accuracy.

Usage:
    python src/generate_expected_csv.py
"""
import csv
import json
import sys
from pathlib import Path

# Add src to path so we can import the shared schema
sys.path.insert(0, str(Path(__file__).parent))
from extract_fields import REDCAP_FIELDS
from build_import_csv import build_fieldnames, flatten_record

# ---------------------------------------------------------------------------
# Ground truth: correct REDCap values for each synthetic note.
# Keys are document_reference_ids matching notes_synthetic.jsonl.
# Format mirrors redcap_fields in notes_redcap.jsonl:
#   - radio/dropdown/yesno/integer/text: string code or None
#   - checkbox: list of string codes ([] if none apply)
# ---------------------------------------------------------------------------
GROUND_TRUTH = {
    # ------------------------------------------------------------------
    # syn-doc-001: Jane D. — Left MTLE-HS, drug-resistant, surgical candidate
    # ------------------------------------------------------------------
    "syn-doc-001": {
        "hand_dom": "2",           # Right
        "sz_age": "19",
        "medhx_etio": "1",         # Focal/multifocal
        "medhx_etio_focal": ["1"], # Mesial temporal sclerosis
        "medhx_szsyndrome": "1",   # Yes
        "medhx_szsyndrome_type": "1",  # MTLE-HS
        "medhx_prior_episgy": "2", # No
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["0"],    # None
        "medhx_psych": ["1", "2"], # Depression, Anxiety
        "medhx_si": "0",
        "medhx_driving": "2",      # No (updated at discharge)
        "medhx_sgy_cand_yn": "1",  # Yes
        "emu_sz_type": "5",        # Focal non-motor with impaired awareness
        "emu_sz_type1_freq": "5",  # Multiple times per month
        "emu_asm_number": "2",
        "emu_asm_type": ["1", "2"],    # levetiracetam, lamotrigine
        "emu_asm_sfx": "3",            # No side effects mentioned
        "emu_asmdc_number": "2",
        "emu_asmdc_type": ["1", "2"],  # same on discharge
        "emu_dcevents_type": "1",      # Epilepsy
        "emu_epilepsytype": "1",       # Focal single focus
        "emu_epilepsy_intract": "1",   # Yes (failed 4 ASMs)
        "emu_sxcandidate": "1",        # Yes, discussed
        "mri_yn": "1",
        "mri_normal_abnormal": "2",    # Abnormal
        "mri_lateralization": "1",     # Left
        "mri_l_localization": "1",     # Temporal
        "mri_r_localization": None,
        "mri_lesion_left": "1",        # Hippocampal sclerosis
        "mri_lesion_right": None,
        "pet_yn": "1",                 # Yes, performed
        "fmri_yn": "2",                # No but ordered
        "wada_yn": "0",                # No (only "may be needed")
    },

    # ------------------------------------------------------------------
    # syn-doc-002: Marcus T. — Pure FND/PNEE, normal MRI
    # ------------------------------------------------------------------
    "syn-doc-002": {
        "hand_dom": "2",           # Right
        "sz_age": "27",
        "medhx_etio": "3",         # PNEE/FND
        "medhx_etio_focal": [],
        "medhx_szsyndrome": "2",   # No
        "medhx_szsyndrome_type": None,
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["0"],    # None
        "medhx_psych": ["4", "1", "2"],  # PTSD, Depression, Anxiety
        "medhx_si": "0",
        "medhx_driving": "2",      # No
        "medhx_sgy_cand_yn": "2",  # No
        "emu_sz_type": None,       # No epileptic seizures
        "emu_sz_type1_freq": None,
        "emu_asm_number": "1",
        "emu_asm_type": ["1"],     # levetiracetam (prescribed incorrectly, to taper)
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "0",   # None (tapering off levetiracetam)
        "emu_asmdc_type": [],
        "emu_dcevents_type": "2",  # FND
        "emu_epilepsytype": None,
        "emu_epilepsy_intract": None,
        "emu_sxcandidate": "5",    # No
        "mri_yn": "1",
        "mri_normal_abnormal": "1",  # Normal
        "mri_lateralization": None,
        "mri_l_localization": None,
        "mri_r_localization": None,
        "mri_lesion_left": None,
        "mri_lesion_right": None,
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-003: Sandra K. — Drug-resistant focal epilepsy, prior VNS, LITT candidate
    # ------------------------------------------------------------------
    "syn-doc-003": {
        "hand_dom": "1",           # Left
        "sz_age": "24",
        "medhx_etio": "1",         # Focal
        "medhx_etio_focal": ["7"], # Cortical dysplasia (FCD)
        "medhx_szsyndrome": "2",   # No
        "medhx_szsyndrome_type": None,
        "medhx_prior_episgy": "1", # Yes
        "medhx_priorepisgy_type": ["12"],  # VNS
        "medhx_neurohx": ["0"],    # None
        "medhx_psych": ["1"],      # Depression
        "medhx_si": "0",
        "medhx_driving": "2",
        "medhx_sgy_cand_yn": "1",  # Yes
        "emu_sz_type": "4",        # Focal motor with impaired awareness
        "emu_sz_type1_freq": "4",  # Weekly
        "emu_asm_number": "3",
        "emu_asm_type": ["15", "9", "7"],  # lacosamide, clobazam, topiramate
        "emu_asm_sfx": "1",        # Yes - dose limiting (topiramate cognitive SFX)
        "emu_asmdc_number": "3",
        "emu_asmdc_type": ["15", "9", "20"],  # lacosamide, clobazam, cenobamate
        "emu_dcevents_type": "1",  # Epilepsy
        "emu_epilepsytype": "1",   # Focal single focus
        "emu_epilepsy_intract": "1",
        "emu_sxcandidate": "1",    # Yes, discussed (LITT + Phase 2)
        "mri_yn": "1",
        "mri_normal_abnormal": "2",
        "mri_lateralization": "2", # Right
        "mri_l_localization": None,
        "mri_r_localization": "2", # Frontal
        "mri_lesion_left": None,
        "mri_lesion_right": "4",   # FCD
        "pet_yn": "1",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-004: Derek M. — JME, medication cross-titration
    # ------------------------------------------------------------------
    "syn-doc-004": {
        "hand_dom": "2",           # Right
        "sz_age": "17",
        "medhx_etio": "0",         # Generalized
        "medhx_etio_focal": [],
        "medhx_szsyndrome": "1",   # Yes
        "medhx_szsyndrome_type": "12",  # JME
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["0"],    # None
        "medhx_psych": ["2"],      # Anxiety
        "medhx_si": "0",
        "medhx_driving": "2",      # No
        "medhx_sgy_cand_yn": "2",  # No
        "emu_sz_type": "9",        # Myoclonus (most frequent - daily)
        "emu_sz_type1_freq": "1",  # Multiple times per day
        "emu_asm_number": "1",
        "emu_asm_type": ["1"],     # levetiracetam
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "2",
        "emu_asmdc_type": ["1", "2"],  # levetiracetam + lamotrigine added
        "emu_dcevents_type": "1",
        "emu_epilepsytype": "4",   # Generalized idiopathic
        "emu_epilepsy_intract": "3",  # Unclear (incomplete control, not formally refractory yet)
        "emu_sxcandidate": "5",    # No
        "mri_yn": "1",
        "mri_normal_abnormal": "1",  # Normal
        "mri_lateralization": None,
        "mri_l_localization": None,
        "mri_r_localization": None,
        "mri_lesion_left": None,
        "mri_lesion_right": None,
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-005: Howard L. — Post-stroke focal epilepsy
    # ------------------------------------------------------------------
    "syn-doc-005": {
        "hand_dom": "2",           # Right
        "sz_age": "67",
        "medhx_etio": "1",         # Focal
        "medhx_etio_focal": ["3"], # Post-stroke/vascular
        "medhx_szsyndrome": "2",
        "medhx_szsyndrome_type": None,
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["1"],    # Ischemic stroke
        "medhx_psych": ["0"],      # None
        "medhx_si": "0",
        "medhx_driving": "2",      # No (since stroke)
        "medhx_sgy_cand_yn": "3",  # Unclear (may be reconsidered)
        "emu_sz_type": "2",        # Focal motor with retained awareness
        "emu_sz_type1_freq": "5",  # Multiple times per month (2-3/month)
        "emu_asm_number": "1",
        "emu_asm_type": ["1"],     # levetiracetam
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "2",
        "emu_asmdc_type": ["1", "15"],  # levetiracetam + lacosamide added
        "emu_dcevents_type": "1",
        "emu_epilepsytype": "1",   # Focal single focus
        "emu_epilepsy_intract": "1",
        "emu_sxcandidate": "4",    # Not currently but possible in future
        "mri_yn": "1",
        "mri_normal_abnormal": "2",
        "mri_lateralization": "2", # Right
        "mri_l_localization": None,
        "mri_r_localization": "1", # Temporal
        "mri_lesion_left": None,
        "mri_lesion_right": "5",   # Stroke/encephalomalacia
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-006: Priya N. — Mixed FND + focal epilepsy, PTSD, history of SI
    # ------------------------------------------------------------------
    "syn-doc-006": {
        "hand_dom": "2",           # Right
        "sz_age": "28",
        "medhx_etio": "5",         # Combined (FND + focal epilepsy)
        "medhx_etio_focal": ["7"], # Cortical dysplasia (possible FCD on MRI)
        "medhx_szsyndrome": "2",
        "medhx_szsyndrome_type": None,
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["0"],
        "medhx_psych": ["4", "1", "2"],  # PTSD, Depression, Anxiety
        "medhx_si": "1",           # Yes (remote history)
        "medhx_driving": "2",
        "medhx_sgy_cand_yn": "2",  # No
        "emu_sz_type": "3",        # Focal non-motor with retained awareness (sensory aura)
        "emu_sz_type1_freq": "3",  # Multiple times per week (1-2/week)
        "emu_asm_number": "1",
        "emu_asm_type": ["4"],     # oxcarbazepine (clonazepam is PRN)
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "1",
        "emu_asmdc_type": ["4"],   # continue oxcarbazepine
        "emu_dcevents_type": "3",  # Mixed FND and epilepsy
        "emu_epilepsytype": "1",   # Focal single focus (left occipital)
        "emu_epilepsy_intract": "3",  # Unclear
        "emu_sxcandidate": "5",    # No
        "mri_yn": "1",
        "mri_normal_abnormal": "2",
        "mri_lateralization": "1", # Left
        "mri_l_localization": "4", # Occipital
        "mri_r_localization": None,
        "mri_lesion_left": "4",    # FCD (possible)
        "mri_lesion_right": None,
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-007: Calvin R. — LGI1 autoimmune limbic encephalitis
    # ------------------------------------------------------------------
    "syn-doc-007": {
        "hand_dom": "2",           # Right
        "sz_age": "53",
        "medhx_etio": "1",         # Focal
        "medhx_etio_focal": ["8"], # Autoimmune/inflammatory
        "medhx_szsyndrome": "2",   # No (autoimmune encephalitis, not a named epilepsy syndrome)
        "medhx_szsyndrome_type": None,
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["4"],    # Dementia/MCI (cognitive decline from encephalitis)
        "medhx_psych": ["0"],      # None
        "medhx_si": "0",
        "medhx_driving": "2",
        "medhx_sgy_cand_yn": "2",  # No
        "emu_sz_type": "5",        # Focal non-motor with impaired awareness
        "emu_sz_type1_freq": "2",  # Daily
        "emu_asm_number": "2",
        "emu_asm_type": ["1", "15"],  # levetiracetam, lacosamide
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "2",
        "emu_asmdc_type": ["1", "15"],
        "emu_dcevents_type": "1",
        "emu_epilepsytype": "1",   # Focal single focus (left temporal onset)
        "emu_epilepsy_intract": "1",
        "emu_sxcandidate": "5",    # No
        "mri_yn": "1",
        "mri_normal_abnormal": "2",
        "mri_lateralization": "3", # Bilateral
        "mri_l_localization": "1", # Temporal
        "mri_r_localization": "1", # Temporal
        "mri_lesion_left": "1",    # Hippocampal signal change (limbic encephalitis)
        "mri_lesion_right": "1",
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },

    # ------------------------------------------------------------------
    # syn-doc-008: Leo W. — Dravet syndrome (SCN1A), adult transition
    # ------------------------------------------------------------------
    "syn-doc-008": {
        "hand_dom": "2",           # Right
        "sz_age": "1",
        "medhx_etio": "2",         # Both focal and generalized
        "medhx_etio_focal": ["9"], # Genetic
        "medhx_szsyndrome": "1",   # Yes
        "medhx_szsyndrome_type": "7",  # Dravet syndrome
        "medhx_prior_episgy": "2",
        "medhx_priorepisgy_type": [],
        "medhx_neurohx": ["0"],    # None (ID/ASD not in neurohx options)
        "medhx_psych": ["0"],      # None (ASD not in psych options)
        "medhx_si": "0",
        "medhx_driving": "2",
        "medhx_sgy_cand_yn": "2",  # No
        "emu_sz_type": "9",        # Myoclonus (most frequent - daily)
        "emu_sz_type1_freq": "1",  # Multiple times per day
        "emu_asm_number": "3",
        "emu_asm_type": ["13", "9", "29"],  # valproic acid, clobazam, fenfluramine
        "emu_asm_sfx": "3",
        "emu_asmdc_number": "3",
        "emu_asmdc_type": ["13", "9", "29"],  # same (cannabidiol discussed but not yet prescribed)
        "emu_dcevents_type": "1",
        "emu_epilepsytype": "5",   # Generalized symptomatic
        "emu_epilepsy_intract": "1",
        "emu_sxcandidate": "5",    # No
        "mri_yn": "1",
        "mri_normal_abnormal": "1",  # Normal
        "mri_lateralization": None,
        "mri_l_localization": None,
        "mri_r_localization": None,
        "mri_lesion_left": None,
        "mri_lesion_right": None,
        "pet_yn": "0",
        "fmri_yn": "0",
        "wada_yn": "0",
    },
}


def main():
    synthetic_path = Path("./data/synthetic/notes_synthetic.jsonl")
    out_path = Path("./data/synthetic/redcap_expected.csv")

    if not synthetic_path.exists():
        raise FileNotFoundError(f"Synthetic notes not found: {synthetic_path}")

    # Load patient metadata from synthetic notes
    notes_meta = {}
    with synthetic_path.open() as f:
        for line in f:
            note = json.loads(line)
            doc_id = note["document_reference_id"]
            notes_meta[doc_id] = {
                "patient_id": note["patient_id"],
                "document_reference_id": doc_id,
                "note_date": note["note_date"],
                "title": note["title"],
            }

    fieldnames = build_fieldnames(REDCAP_FIELDS)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    missing = []
    with out_path.open("w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for doc_id, gt_fields in GROUND_TRUTH.items():
            if doc_id not in notes_meta:
                missing.append(doc_id)
                continue
            meta = notes_meta[doc_id]
            row = {**meta, "redcap_fields": gt_fields}
            flat = flatten_record(row, fieldnames)
            writer.writerow(flat)
            written += 1

    print(f"Wrote {written} ground truth rows → {out_path}")
    if missing:
        print(f"Warning: no metadata found for: {missing}")


if __name__ == "__main__":
    main()
