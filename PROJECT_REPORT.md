---
layout: page
title: Clinical Notes Pipeline
description: Automated REDCap data extraction from Epic FHIR clinical notes using a local LLM — no PHI leaves the machine.
img: assets/img/projects/redcap_accuracy.png
importance: 1
category: work
tags: [python, nlp, healthcare, epic, fhir, ollama, redcap, llm]
---

## Overview

Epilepsy surgery programs rely on detailed research databases to track patient outcomes. At our institution, clinicians manually enter data from EMU (Epilepsy Monitoring Unit) discharge summaries into REDCap — a process that is time-consuming and prone to transcription error.

This project builds an end-to-end ETL pipeline that automatically extracts structured REDCap fields from Epic FHIR clinical notes using a locally-running large language model. Because all inference runs on-device via [Ollama](https://ollama.com), no patient data is transmitted to external APIs.

---

## Pipeline Architecture

```
Epic FHIR API
     │
     ▼
extract_epic_notes.py       → Raw JSONL (PDF, HTML, RTF, plain text)
     │
     ▼
clean_note_text.py          → Cleaned plain text JSONL
     │
     ▼
summarize_with_ollama.py    → LLM summary JSONL (chief complaint, diagnoses, meds)
     │
     ▼
extract_redcap_fields.py    → 30+ REDCap fields extracted per note
     │
     ▼
build_redcap_csv.py         → redcap_import.csv (ready for REDCap Data Import Tool)
```

**Key components:**

- **Epic FHIR integration** — supports `open`, `token`, and `backend` (RS256 JWT) authentication modes. Fetches `DocumentReference` resources and downloads `Binary` attachments.
- **Multi-format parsing** — handles PDF (pypdf), HTML, RTF, and plain text note formats.
- **Two-pass LLM extraction** — pass 1 produces a general clinical summary; pass 2 is a targeted REDCap extraction using the full note text and a field-specific prompt.
- **Grouped prompts** — the 30+ REDCap fields are split into 5 focused groups (medical history, seizure, ASMs, discharge, imaging), each sent as a separate Ollama call. This keeps prompts focused and reduces hallucination from context overload.
- **Post-processing normalization** — model output is normalized to valid REDCap codes, handling label→code mapping, boolean strings, and stringified lists.

---

## REDCap Field Schema

The pipeline targets 30+ variables from the EMU Epilepsy Surgery Utilization data dictionary, spanning:

| Domain | Fields |
|---|---|
| Medical History | Handedness, seizure onset age, seizure etiology, epilepsy syndrome, prior surgery, neurological/psychiatric comorbidities, suicidal ideation, driving status, surgical candidacy |
| Seizure | Primary seizure type/semiology, seizure frequency |
| Medications | ASMs on admission and discharge (name + count), side effects |
| EMU Discharge | Discharge diagnosis, epilepsy type/localization, medical refractory status, surgical candidacy |
| Imaging | MRI (performed, result, lateralization, localization, lesion type), FDG-PET, fMRI, WADA |

Checkbox fields (multi-select) are expanded into `fieldname___code` columns — REDCap's required import format.

---

## Accuracy Improvement

Model performance was evaluated against 8 synthetic EMU discharge notes with hand-labeled ground truth. Accuracy was tracked across four iterations:

| Iteration | Change | Avg Accuracy |
|---|---|---|
| llama3.2:3b (baseline) | Initial model | ~23.5%* |
| mistral-nemo:12b | Model upgrade | 72.0% |
| Round 1 fixes | Post-processing defaults, prompt disambiguation for neurohx/etio/frequency | 79.2% |
| Round 2 fixes | medhx_szsyndrome default, myoclonus instruction | 82.5% |

*Single-select fields only; checkbox 0s inflate raw accuracy significantly.

### Round 1 Fix Details
- **Post-processing defaults:** For fields where absence of mention reliably means "No" (WADA, fMRI, FDG-PET, ASM side effects), null model outputs are defaulted to the "No" code rather than left blank.
- **Neurological comorbidity disambiguation:** Added explicit instruction that seizure etiology (e.g., post-stroke epilepsy) does not imply stroke as a current neurological comorbidity.
- **Seizure etiology codes:** Added per-code examples to prevent confusion between focal, generalized, mixed, and PNEE classifications.
- **Frequency anchors:** Mapped exact phrases to frequency codes (e.g., "2-3x/month" → code 5).

### Round 2 Fix Details
- **Epilepsy syndrome default:** When the model returns null for `medhx_szsyndrome`, default to "No confirmed syndrome" — the correct answer in the majority of cases.
- **Myoclonus instruction:** Explicitly clarified that myoclonic jerks in JME and Dravet syndrome are code 9 (Myoclonus), not code 1 (Primary GTC).

### Current Accuracy by Field

{% include figure.liquid loading="eager" path="assets/img/projects/redcap_accuracy.png" class="img-fluid rounded z-depth-1" caption="Field-level extraction accuracy (mistral-nemo:12B, n=8 synthetic EMU notes). Average: 82.5%." %}

---

## Key Technical Decisions

**Local LLM inference (Ollama):** All model inference runs on-device. No patient data is sent to OpenAI, Anthropic, or any external API. This is a hard requirement for clinical research data.

**Grouped prompts over one large prompt:** Early experiments with a single prompt for all 30+ fields produced worse results than splitting into 5 focused groups. Shorter prompts improve instruction following, especially for a 12B model.

**Post-processing normalization layer:** Rather than relying solely on the model to output valid codes, a normalization pass maps text labels to codes, unwraps complex objects (dicts, stringified lists), and applies clinically justified defaults. This separates extraction from formatting concerns.

**Synthetic test notes for evaluation:** Using 8 hand-crafted synthetic EMU notes allows rapid iteration without PHI exposure. Each note covers a distinct clinical scenario (MTLE-HS, FND/PNEE, Dravet, JME, autoimmune epilepsy, post-stroke epilepsy, mixed FND+epilepsy, drug-resistant focal epilepsy).

---

## Remaining Challenges

- **`emu_asmdc_number` (38%):** The model reliably counts admission ASMs but struggles with discharge ASM counts. The discharge medication section appears in different locations across notes and the model loses track of which list it's counting.
- **`sz_age` (50%):** Age at seizure onset is frequently confused with the patient's current age, or missed entirely when phrased indirectly (e.g., "epilepsy since childhood").
- **Model stochasticity:** Results vary slightly between runs because LLM inference is non-deterministic. Some fields that pass one run fail the next. Setting `temperature=0` in the Ollama call would improve reproducibility.
- **Overfitting risk:** Every prompt improvement is validated against only 8 synthetic notes. Adding more diverse synthetic cases is the next priority before production use.

---

## Code & Setup

**GitHub:** [stephenchen06/clinical-notes-pipeline](https://github.com/stephenchen06/clinical-notes-pipeline)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add Epic credentials + Ollama settings
ollama serve && ollama pull mistral-nemo
python src/run_pipeline.py
```

To evaluate against synthetic notes:
```bash
python src/evaluate_pipeline.py
```

---

<!--
================================================================================
HANDOFF INSTRUCTIONS FOR WEBSITE CLAUDE
================================================================================
This file is pre-formatted as a Jekyll al-folio _projects/ page.

Steps to add this to the website:
1. Read AGENTS.md in the website repo before making any changes
2. Copy this file to:
       _projects/clinical-notes-pipeline.md
   (remove this HANDOFF INSTRUCTIONS comment block before copying)
3. Copy the accuracy chart image from the pipeline repo:
       clinical_notes_pipeline/data/reports/redcap_accuracy.png
   to the website repo at:
       assets/img/projects/redcap_accuracy.png
   (create the projects/ subdirectory if it does not exist)
4. The img: field in the front matter already points to:
       assets/img/projects/redcap_accuracy.png
   No changes needed there.
5. The figure.liquid include in the "Current Accuracy by Field" section
   also references assets/img/projects/redcap_accuracy.png — no changes needed.
6. Commit both files and push.
================================================================================
-->
