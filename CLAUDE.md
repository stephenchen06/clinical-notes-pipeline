# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Epic credentials, patient IDs, and Ollama settings
```

Ollama must be running locally for the summarization and REDCap extraction steps:
```bash
ollama serve
ollama pull mistral-nemo  # current model — do not change without re-evaluating accuracy
```

## Running the Pipeline

Full pipeline (runs all steps sequentially):
```bash
python src/run_pipeline.py
```

Individual steps:
```bash
python src/extract_epic_notes.py       # Extract from Epic FHIR → data/raw/notes_raw.jsonl
python src/clean_note_text.py          # Clean HTML/RTF → data/processed/notes_clean.jsonl
python src/summarize_with_ollama.py    # LLM summarize → data/processed/notes_summaries.jsonl
python src/build_csv.py                # Export → data/processed/notes_summary.csv
python src/extract_fields.py   # REDCap extraction → data/processed/notes_redcap.jsonl
python src/build_import_csv.py         # REDCap import CSV → data/processed/redcap_import.csv
```

Evaluate accuracy against synthetic notes (runs all 4 eval steps):
```bash
python src/load_synthetic_notes.py     # Load synthetic notes into pipeline
python src/evaluate_pipeline.py        # extract → build → evaluate → visualize
```

Diagnose Epic 403 authentication errors:
```bash
python src/diagnose_epic_403.py
```

## Architecture

This is a linear ETL pipeline: Epic FHIR API → raw JSONL → cleaned JSONL → LLM-summarized JSONL → CSV → REDCap import CSV.

**`extract_epic_notes.py`** — `EpicFHIRClient` class handles Epic FHIR authentication (3 modes: `open`, `token`, `backend`). Backend mode uses RS256 JWT assertions via `PyJWT` + `cryptography`. Fetches `DocumentReference` resources and downloads `Binary` attachments. Parses PDF (via `pypdf`), HTML, RTF, and plain text. Outputs flat JSONL records with fields: `patient_id`, `document_reference_id`, `note_date`, `title`, `content_type`, `source_url`, `note_text`.

**`clean_note_text.py`** — Regex-based cleaning: strips HTML tags (inserting newlines for block elements), removes RTF control sequences, normalizes whitespace. Appends `note_text_clean` field to each record.

**`summarize_with_ollama.py`** — Calls local Ollama `/api/generate` (180s timeout). Prompts the model to return structured JSON with: `summary`, `chief_complaint`, `key_diagnoses[]`, `medications[]`, `follow_up`, `red_flags[]`. Includes JSON recovery logic to extract `{...}` from markdown-wrapped responses and phrase-based validation to mark invalid/insufficient outputs as `"NA"`.

**`build_csv.py`** — Converts JSONL to CSV. Array fields (`key_diagnoses`, `medications`, `red_flags`) are pipe-separated.

**`extract_fields.py`** — Second LLM extraction pass targeting the clinician's REDCap data dictionary (`EMUEpilepsySurgeryUtilization_DataDictionary_2026-03-03.csv`). Key design decisions:
- `REDCAP_FIELDS`: hardcoded schema of 30+ variables (medical history, seizure type, ASMs, discharge diagnosis, surgical candidacy, MRI)
- `GROUP_FIELDS`: fields split into 5 focused groups (medical_history, seizure, asms, discharge, imaging) — each group is a separate Ollama call to keep prompts focused
- `GROUP_INSTRUCTIONS`: per-group special instructions injected into the prompt to address known model failure patterns (e.g., neurohx disambiguation, frequency anchors, myoclonus vs GTC)
- `FIELD_DEFAULTS`: post-processing defaults applied when model returns null for fields where absence = "No" (pet_yn, fmri_yn, wada_yn, emu_asm_sfx, medhx_szsyndrome)
- `normalize_fields()`: maps model output (text labels, booleans, complex objects) to valid REDCap codes
- Checkbox fields return arrays of codes; radio/dropdown fields return a single code string or null
- Outputs `notes_redcap.jsonl`

**`build_import_csv.py`** — Converts `notes_redcap.jsonl` to `redcap_import.csv` in REDCap's import format. Checkbox fields are expanded to `fieldname___code` columns with 1/0 values (REDCap's required format). The output CSV can be uploaded directly via REDCap's Data Import Tool.

**`evaluate_pipeline.py`** — Helper script that runs all 4 evaluation steps sequentially: `extract_fields.py` → `build_import_csv.py` → `evaluate_extraction.py` → `visualize_accuracy.py`.

**`evaluate_extraction.py`** — Compares `data/processed/redcap_import.csv` against `data/synthetic/redcap_expected.csv`. Outputs per-field and per-patient accuracy with detailed mismatch diffs.

**`visualize_accuracy.py`** — Generates `data/reports/redcap_accuracy.png` — a horizontal bar chart of field-level accuracy grouped by clinical domain.

## Accuracy Status

Current model: `mistral-nemo:latest` (12B). Accuracy on 8 synthetic EMU notes:

| Iteration | Change | Avg Accuracy |
|---|---|---|
| llama3.2:3b | Initial model | ~23.5% (single-select only) |
| mistral-nemo | Model upgrade | 72.0% |
| Round 1 | Post-processing defaults, prompt disambiguation | 79.2% |
| Round 2 | medhx_szsyndrome default, myoclonus instruction | 82.5% |

**Known weak fields:** `emu_asmdc_number` (38%), `sz_age` (50%), `emu_sz_type1_freq` (50%), `mri_l_localization` (50%).

**Known default backfire risk:** `FIELD_DEFAULTS` can wrongly override a positive finding if the model returns null. Affects `emu_asm_sfx` (doc-003: side effects present but defaulted to "None") and `medhx_szsyndrome` (doc-003, doc-007: model over-eagerly returns "Yes"). Monitor these when adding new notes.

## Configuration

All runtime config lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `EPIC_AUTH_METHOD` | `open`, `token`, or `backend` |
| `EPIC_ACCESS_TOKEN` | Bearer token (token mode) |
| `EPIC_CLIENT_ID` / `EPIC_PRIVATE_KEY_PATH` | JWT credentials (backend mode) |
| `EPIC_PATIENT_IDS` | Comma-separated patient FHIR IDs |
| `DOCUMENT_REFERENCE_IDS` | Directly fetch specific document IDs (bypasses search) |
| `OLLAMA_MODEL` | Local model name (default: `mistral-nemo`) |
| `RAW_NOTES_JSONL` / `CLEAN_NOTES_JSONL` / `SUMMARIES_JSONL` / `OUTPUT_CSV` | Output file paths |
| `REDCAP_JSONL` / `REDCAP_CSV` | REDCap extraction output paths |

The `secrets/` directory and `.env` are git-ignored. Private keys go in `secrets/`.

## Test Data

- `data/synthetic/notes_synthetic.jsonl` — 8 synthetic EMU discharge notes (no PHI)
- `data/synthetic/redcap_expected.csv` — ground truth REDCap values for evaluation
- `data/reports/redcap_accuracy.png` — latest accuracy chart (committed to git)

## Git Workflow

Commit the accuracy chart whenever evaluation is re-run so GitHub reflects the latest results:
```bash
git add data/reports/redcap_accuracy.png src/extract_fields.py
git commit -m "describe what changed and accuracy delta"
git push
```
