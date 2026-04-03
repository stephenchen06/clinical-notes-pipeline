# Clinical Notes Pipeline: Epic FHIR → REDCap via Local LLM

An end-to-end ETL pipeline that extracts clinical notes from **Epic FHIR**, cleans and summarizes them using a **local LLM (Ollama)**, and automatically extracts structured fields for **REDCap** import — all without sending patient data to external APIs.

Built for an Epilepsy Monitoring Unit (EMU) research workflow to auto-populate a REDCap data dictionary from clinical documentation.

## Architecture

```
Epic FHIR API
     │
     ▼
extract_epic_notes.py       → data/raw/notes_raw.jsonl
     │
     ▼
clean_note_text.py          → data/processed/notes_clean.jsonl
     │
     ▼
summarize_with_ollama.py    → data/processed/notes_summaries.jsonl
     │
     ├──▶ build_csv.py      → data/processed/notes_summary.csv
     │
     ▼
extract_redcap_fields.py    → data/processed/notes_redcap.jsonl
     │
     ▼
build_redcap_csv.py         → data/processed/redcap_import.csv
                               (ready for REDCap Data Import Tool)
```

## Features

- **Epic FHIR integration** — supports `open`, `token`, and `backend` (RS256 JWT) auth modes
- **Multi-format parsing** — handles PDF (pypdf), HTML, RTF, and plain text attachments
- **Local LLM summarization** — runs entirely on-device via Ollama; no PHI leaves the machine
- **Structured REDCap extraction** — 30+ fields across medical history, seizure type, ASMs, discharge diagnosis, surgical candidacy, and MRI
- **Checkbox field expansion** — outputs `fieldname___code` columns in REDCap's required import format
- **Accuracy evaluation** — field-by-field comparison against ground truth with visualization

## Accuracy (mistral-nemo:12B, n=8 synthetic EMU notes)

![REDCap Field Extraction Accuracy](data/reports/redcap_accuracy.png)

**Average accuracy: 72%** across 30+ REDCap fields. Strong performance on MRI fields (100%), medication extraction (95–99%), and seizure etiology (99%). Active work ongoing to improve numeric field extraction (seizure frequency, age at onset) and low-frequency procedure fields (WADA, fMRI).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Epic credentials, patient IDs, and Ollama settings
```

Ollama must be running locally:

```bash
ollama serve
ollama pull mistral-nemo
```

## Running the Pipeline

**Full pipeline:**
```bash
python src/run_pipeline.py
```

**Individual steps:**
```bash
python src/extract_epic_notes.py       # Epic FHIR → data/raw/notes_raw.jsonl
python src/clean_note_text.py          # Clean HTML/RTF → data/processed/notes_clean.jsonl
python src/summarize_with_ollama.py    # LLM summarize → data/processed/notes_summaries.jsonl
python src/build_csv.py                # → data/processed/notes_summary.csv
python src/extract_redcap_fields.py   # REDCap extraction → data/processed/notes_redcap.jsonl
python src/build_redcap_csv.py         # REDCap import CSV → data/processed/redcap_import.csv
```

**Evaluate against synthetic test data:**
```bash
python src/load_synthetic_notes.py     # Load test notes into pipeline
python src/generate_expected_csv.py    # Generate ground truth CSV
python src/evaluate_redcap_extraction.py
python src/visualize_accuracy.py       # → data/reports/redcap_accuracy.png
```

**Diagnose Epic auth errors:**
```bash
python src/diagnose_epic_403.py
```

## Configuration

All runtime config lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `EPIC_AUTH_METHOD` | `open`, `token`, or `backend` |
| `EPIC_ACCESS_TOKEN` | Bearer token (token mode) |
| `EPIC_CLIENT_ID` / `EPIC_PRIVATE_KEY_PATH` | JWT credentials (backend mode) |
| `EPIC_PATIENT_IDS` | Comma-separated patient FHIR IDs |
| `DOCUMENT_REFERENCE_IDS` | Directly fetch specific document IDs |
| `OLLAMA_MODEL` | Local model name (e.g. `mistral-nemo`) |
| `RAW_NOTES_JSONL` / `CLEAN_NOTES_JSONL` / `SUMMARIES_JSONL` / `OUTPUT_CSV` | Output paths |
| `REDCAP_JSONL` / `REDCAP_CSV` | REDCap extraction output paths |

The `secrets/` directory and `.env` are git-ignored. Private keys go in `secrets/`.

## Privacy

All LLM inference runs locally via Ollama. No patient data is sent to external APIs. `data/raw/` and `data/processed/` are excluded from version control.
