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

Ollama must be running locally for the summarization step:
```bash
ollama serve
ollama pull llama3.1:8b
```

## Running the Pipeline

Full pipeline (runs all steps sequentially):
```bash
python src/run_pipeline.py
```

Individual steps:
```bash
python src/extract_epic_notes.py       # Extract from Epic FHIR → data/raw/notes_raw.jsonl
python src/clean_note_text.py           # Clean HTML/RTF → data/processed/notes_clean.jsonl
python src/summarize_with_ollama.py     # LLM summarize → data/processed/notes_summaries.jsonl
python src/build_csv.py                 # Export → data/processed/notes_summary.csv
python src/extract_redcap_fields.py    # REDCap extraction → data/processed/notes_redcap.jsonl
python src/build_redcap_csv.py          # REDCap import CSV → data/processed/redcap_import.csv
```

Diagnose Epic 403 authentication errors:
```bash
python src/diagnose_epic_403.py
```

## Architecture

This is a linear ETL pipeline: Epic FHIR API → raw JSONL → cleaned JSONL → LLM-summarized JSONL → CSV.

**`extract_epic_notes.py`** — `EpicFHIRClient` class handles Epic FHIR authentication (3 modes: `open`, `token`, `backend`). Backend mode uses RS256 JWT assertions via `PyJWT` + `cryptography`. Fetches `DocumentReference` resources and downloads `Binary` attachments. Parses PDF (via `pypdf`), HTML, RTF, and plain text. Outputs flat JSONL records with fields: `patient_id`, `document_reference_id`, `note_date`, `title`, `content_type`, `source_url`, `note_text`.

**`clean_note_text.py`** — Regex-based cleaning: strips HTML tags (inserting newlines for block elements), removes RTF control sequences, normalizes whitespace. Appends `note_text_clean` field to each record.

**`summarize_with_ollama.py`** — Calls local Ollama `/api/generate` (180s timeout). Prompts the model to return structured JSON with: `summary`, `chief_complaint`, `key_diagnoses[]`, `medications[]`, `follow_up`, `red_flags[]`. Includes JSON recovery logic to extract `{...}` from markdown-wrapped responses and phrase-based validation to mark invalid/insufficient outputs as `"NA"`.

**`build_csv.py`** — Converts JSONL to CSV. Array fields (`key_diagnoses`, `medications`, `red_flags`) are pipe-separated.

**`extract_redcap_fields.py`** — Second LLM extraction pass targeting the clinician's REDCap data dictionary (`EMUEpilepsySurgeryUtilization_DataDictionary_2026-03-03.csv`). The field schema is hardcoded in `REDCAP_FIELDS` (30+ variables across medical history, seizure type, ASMs, discharge diagnosis, surgical candidacy, and MRI). The prompt gives the model constrained options (coded values) for each categorical field. Checkbox fields return arrays of codes; radio/dropdown fields return a single code string or null. Outputs `notes_redcap.jsonl`.

**`build_redcap_csv.py`** — Converts `notes_redcap.jsonl` to `redcap_import.csv` in REDCap's import format. Checkbox fields are expanded to `fieldname___code` columns with 1/0 values (REDCap's required format). The output CSV can be uploaded directly via REDCap's Data Import Tool.

## Configuration

All runtime config lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `EPIC_AUTH_METHOD` | `open`, `token`, or `backend` |
| `EPIC_ACCESS_TOKEN` | Bearer token (token mode) |
| `EPIC_CLIENT_ID` / `EPIC_PRIVATE_KEY_PATH` | JWT credentials (backend mode) |
| `EPIC_PATIENT_IDS` | Comma-separated patient IDs to search |
| `DOCUMENT_REFERENCE_IDS` | Directly fetch specific document IDs (bypasses search) |
| `OLLAMA_MODEL` | Local model name (default: `llama3.1:8b`) |
| `RAW_NOTES_JSONL` / `CLEAN_NOTES_JSONL` / `SUMMARIES_JSONL` / `OUTPUT_CSV` | Output file paths |
| `REDCAP_JSONL` / `REDCAP_CSV` | REDCap extraction output paths |

The `secrets/` directory and `.env` are git-ignored. Private keys go in `secrets/`.
