#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Dict

import requests
from dotenv import load_dotenv

INVALID_OUTPUT_PHRASES = [
    "not a valid note",
    "not valid note",
    "invalid note",
    "cannot summarize",
    "can't summarize",
    "unable to summarize",
    "insufficient information",
    "no clinical note",
]


def build_prompt(note: Dict) -> str:
    text = note.get("note_text_clean") or note.get("note_text", "")
    return f"""
You are a clinical note summarizer.
Return STRICT JSON only with keys:
- summary
- chief_complaint
- key_diagnoses (array of strings)
- medications (array of strings)
- follow_up (string)
- red_flags (array of strings)

If an item is missing, use empty string or empty list.
Keep summary concise (max 120 words).

Clinical note:
{text}
""".strip()


def call_ollama(base_url: str, model: str, prompt: str) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("response", "")


def parse_json_or_fallback(raw: str) -> Dict:
    # Try direct JSON parse first.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Recover JSON if the model wraps output with markdown/text.
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return {
        "summary": raw.strip(),
        "chief_complaint": "",
        "key_diagnoses": [],
        "medications": [],
        "follow_up": "",
        "red_flags": [],
    }


def na_payload() -> Dict:
    return {
        "summary": "NA",
        "chief_complaint": "NA",
        "key_diagnoses": ["NA"],
        "medications": ["NA"],
        "follow_up": "NA",
        "red_flags": ["NA"],
    }


def normalize_structured_fields(structured: Dict) -> Dict:
    out = {}
    out["summary"] = str(structured.get("summary", "") or "").strip()
    out["chief_complaint"] = str(structured.get("chief_complaint", "") or "").strip()
    out["follow_up"] = str(structured.get("follow_up", "") or "").strip()

    for key in ("key_diagnoses", "medications", "red_flags"):
        value = structured.get(key, [])
        if isinstance(value, list):
            cleaned = [str(v).strip() for v in value if str(v).strip()]
            out[key] = cleaned
        elif value is None:
            out[key] = []
        else:
            text = str(value).strip()
            out[key] = [text] if text else []

    return out


def should_replace_with_na(structured: Dict, raw_response: str) -> bool:
    combined_text = " ".join(
        [
            raw_response or "",
            structured.get("summary", ""),
            structured.get("chief_complaint", ""),
            structured.get("follow_up", ""),
            " ".join(structured.get("key_diagnoses", [])),
            " ".join(structured.get("medications", [])),
            " ".join(structured.get("red_flags", [])),
        ]
    ).lower()

    if any(phrase in combined_text for phrase in INVALID_OUTPUT_PHRASES):
        return True

    # Treat effectively empty structured output as unusable.
    no_text = (
        not structured.get("summary")
        and not structured.get("chief_complaint")
        and not structured.get("follow_up")
        and not structured.get("key_diagnoses")
        and not structured.get("medications")
        and not structured.get("red_flags")
    )
    return no_text


def main():
    load_dotenv()

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    raw_path = Path(os.getenv("RAW_NOTES_JSONL", "./data/raw/notes_raw.jsonl"))
    clean_path = Path(os.getenv("CLEAN_NOTES_JSONL", "./data/processed/notes_clean.jsonl"))
    out_path = Path(os.getenv("SUMMARIES_JSONL", "./data/processed/notes_summaries.jsonl"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not raw_path.exists() and not clean_path.exists():
        raise FileNotFoundError(f"Raw notes file not found: {raw_path}")
    in_path = clean_path if clean_path.exists() else raw_path

    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            note = json.loads(line)
            prompt = build_prompt(note)
            raw_response = call_ollama(base_url, model, prompt)
            structured = parse_json_or_fallback(raw_response)
            structured = normalize_structured_fields(structured)

            if should_replace_with_na(structured, raw_response):
                structured = na_payload()

            row = {
                "patient_id": note.get("patient_id", ""),
                "document_reference_id": note.get("document_reference_id", ""),
                "note_date": note.get("note_date", ""),
                "title": note.get("title", ""),
                "summary": structured.get("summary", ""),
                "chief_complaint": structured.get("chief_complaint", ""),
                "key_diagnoses": structured.get("key_diagnoses", []),
                "medications": structured.get("medications", []),
                "follow_up": structured.get("follow_up", ""),
                "red_flags": structured.get("red_flags", []),
            }
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} summaries to {out_path}")


if __name__ == "__main__":
    main()
