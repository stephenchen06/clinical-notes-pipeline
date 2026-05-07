# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Epic credentials, patient IDs, and inference backend settings
```

For local inference, Ollama must be running:
```bash
ollama serve
ollama pull ministral-3:14b  # current target local model (9.1GB)
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
python src/extract_fields.py           # Field extraction → data/processed/notes_redcap.jsonl
python src/build_import_csv.py         # Import CSV → data/processed/redcap_import.csv
```

Evaluate accuracy against synthetic notes (runs all 4 eval steps):
```bash
python src/load_synthetic_notes.py     # Load synthetic notes into pipeline
python src/evaluate_pipeline.py        # extract → build → evaluate → visualize
```

To run on a single note without disturbing the full eval:
```bash
grep "real-doc-001" data/synthetic/notes_synthetic.jsonl > data/processed/notes_real_only.jsonl
# Set CLEAN_NOTES_JSONL=./data/processed/notes_real_only.jsonl in .env
python src/extract_fields.py
python src/build_import_csv.py
python src/evaluate_extraction.py
# Revert CLEAN_NOTES_JSONL when done
```

Diagnose Epic 403 authentication errors:
```bash
python src/diagnose_epic_403.py
```

## Architecture

This is a linear ETL pipeline: Epic FHIR API → raw JSONL → cleaned JSONL → import CSV.

**`extract_epic_notes.py`** — `EpicFHIRClient` class handles Epic FHIR authentication (3 modes: `open`, `token`, `backend`). Backend mode uses RS256 JWT assertions via `PyJWT` + `cryptography`. Fetches `DocumentReference` resources and downloads `Binary` attachments. Parses PDF (via `pypdf`), HTML, RTF, and plain text. Outputs flat JSONL records with fields: `patient_id`, `document_reference_id`, `note_date`, `title`, `content_type`, `source_url`, `note_text`.

**`clean_note_text.py`** — Regex-based cleaning: strips HTML tags (inserting newlines for block elements), removes RTF control sequences, normalizes whitespace. Appends `note_text_clean` field to each record.

**`extract_fields.py`** — LLM extraction from cleaned note text, targeting the EMU data dictionary (`EMUEpilepsySurgeryUtilization_DataDictionary_2026-03-03.csv`). Supports two inference backends controlled by `INFERENCE_BACKEND` in `.env`. Key design decisions:
- `REDCAP_FIELDS`: hardcoded schema of 30+ variables (medical history, seizure type, ASMs, discharge diagnosis, surgical candidacy, MRI)
- `GROUP_FIELDS`: fields split into 5 focused groups (medical_history, seizure, asms, discharge, imaging) — each group is a separate LLM call to keep prompts focused
- `GROUP_INSTRUCTIONS`: per-group special instructions injected into the prompt to address known model failure patterns (e.g., neurohx disambiguation, frequency anchors, myoclonus vs GTC)
- `FIELD_DEFAULTS`: post-processing defaults applied when model returns null for fields where absence = "No" (pet_yn, fmri_yn, wada_yn, emu_asm_sfx, medhx_szsyndrome)
- `normalize_fields()`: maps model output (text labels, booleans, complex objects) to valid REDCap codes
- `call_ollama()` / `call_mistral()`: backend functions — routed by `INFERENCE_BACKEND` env var
- Both backends use `temperature=0` for reproducibility
- Checkbox fields return arrays of codes; radio/dropdown fields return a single code string or null
- Outputs `notes_redcap.jsonl`

**`build_import_csv.py`** — Converts `notes_redcap.jsonl` to `redcap_import.csv` in REDCap's import format. Checkbox fields are expanded to `fieldname___code` columns with 1/0 values (REDCap's required format). The output CSV can be uploaded directly via REDCap's Data Import Tool.

**`evaluate_pipeline.py`** — Helper script that runs all 4 evaluation steps sequentially: `extract_fields.py` → `build_import_csv.py` → `evaluate_extraction.py` → `visualize_accuracy.py`. Note: starts with `load_synthetic_notes.py` which overwrites `notes_clean.jsonl` — do not use when testing a single note.

**`evaluate_extraction.py`** — Compares `data/processed/redcap_import.csv` against `data/synthetic/redcap_expected.csv`. Outputs per-field and per-patient accuracy with detailed mismatch diffs.

**`visualize_accuracy.py`** — Generates `data/reports/redcap_accuracy.png` — a horizontal bar chart of field-level accuracy grouped by clinical domain.

## Accuracy Status

| Iteration | Model | Change | Avg Accuracy |
|---|---|---|---|
| llama3.2:3b (local) | 3B | Initial model | ~23.5% (single-select only) |
| mistral-nemo (local) | 12B | Model upgrade | 72.0% |
| mistral-nemo (local) | 12B | Post-processing defaults, prompt disambiguation | 79.2% |
| mistral-nemo (local) | 12B | medhx_szsyndrome default, myoclonus instruction | 82.5% |
| ministral-14b-latest (API) | 14B | Model upgrade via Mistral la Plateforme | **97.6%** |

Target local model: `ministral-3:14b` (Ollama) — same weights as `ministral-14b-latest`, Q4_K_M quantized, 9.1GB. Expected ~95-96% locally due to quantization.

**Remaining weak fields (at 97.6%):** `sz_age` (75%), `emu_sz_type1_freq` (75%), `emu_asmdc_number` (75%), `emu_epilepsy_intract` (75%), `mri_lesion_left` (75%).

**Known default backfire risk:** `FIELD_DEFAULTS` can wrongly override a positive finding if the model returns null. Affects `emu_asm_sfx` (doc-003) and `medhx_szsyndrome` (doc-003, doc-007). Monitor when adding new notes.

## Configuration

All runtime config lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `INFERENCE_BACKEND` | `ollama` (local) or `mistral` (la Plateforme API) |
| `OLLAMA_MODEL` | Local Ollama model (default: `ministral-3:14b`) |
| `MISTRAL_API_KEY` | Mistral la Plateforme API key |
| `MISTRAL_MODEL` | Mistral API model (default: `ministral-14b-latest`) |
| `EPIC_AUTH_METHOD` | `open`, `token`, or `backend` |
| `EPIC_ACCESS_TOKEN` | Bearer token (token mode) |
| `EPIC_CLIENT_ID` / `EPIC_PRIVATE_KEY_PATH` | JWT credentials (backend mode) |
| `EPIC_PATIENT_IDS` | Comma-separated patient FHIR IDs |
| `DOCUMENT_REFERENCE_IDS` | Directly fetch specific document IDs (bypasses search) |
| `RAW_NOTES_JSONL` / `CLEAN_NOTES_JSONL` | Output paths for extraction and cleaning steps |
| `REDCAP_JSONL` / `REDCAP_CSV` | Field extraction output paths |

The `secrets/` directory and `.env` are git-ignored. Private keys go in `secrets/`.

## Test Data

- `data/synthetic/notes_synthetic.jsonl` — 8 synthetic EMU discharge notes + 1 real de-identified admission note (real-doc-001)
- `data/synthetic/redcap_expected.csv` — ground truth REDCap values for evaluation (9 notes)
- `data/reports/redcap_accuracy.png` — latest accuracy chart (committed to git)

Note IDs: `syn-doc-001` through `syn-doc-008` are synthetic discharge summaries. `real-doc-001` is a real de-identified EMU admission note — ground truth was generated by Claude Opus from the note text.

## Next Steps (as of 2026-04-13)

- **Establish validated ground truth** — the current `redcap_expected.csv` was AI-generated (ChatGPT for synthetic notes, Claude Opus for real-doc-001), not clinician-verified. 97.6% accuracy is against this AI answer key, not a clinical gold standard. Blocked on Dr. Belfin / Dr. Waters reviewing the expected CSV or providing real coded notes. See `SUPERVISOR_BRIEFING_040926.md` for the ask.
- **Pull and benchmark `ministral-3:14b` locally** — `ollama pull ministral-3:14b` — expected ~95-96% accuracy (same model as API, Q4_K_M quantized). Holding until ground truth is validated.
- **Improve remaining weak fields** — targeted prompt fixes for `mri_lesion_left/right` (add clinical aliases: MTS/HS → code 1, FCD → code 4), `emu_epilepsy_intract` (tighten "Unclear" vs "Yes" boundary), `emu_sz_type1_freq` (more frequency anchors), `sz_age` (more directive onset age instructions).
- **Expand synthetic test set to 20–30 notes** — get non-PHI notes from Dr. Waters. Priority: edge cases for weak fields.
- **Validation on real notes** — once Epic access is established, run de-identified real notes to verify accuracy outside the synthetic environment.

## Git Workflow

Commit the accuracy chart whenever evaluation is re-run so GitHub reflects the latest results:
```bash
git add data/reports/redcap_accuracy.png src/extract_fields.py
git commit -m "describe what changed and accuracy delta"
git push
```
