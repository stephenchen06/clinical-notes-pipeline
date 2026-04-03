#!/usr/bin/env python3
import html
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv


TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"[ \t]+")
MULTINEWLINE_RE = re.compile(r"\n{3,}")
RTF_CTRL_RE = re.compile(r"\\[a-zA-Z]+-?\d* ?")
RTF_HEX_RE = re.compile(r"\\'[0-9a-fA-F]{2}")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = MULTISPACE_RE.sub(" ", text)
    text = MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()


def clean_html_text(text: str) -> str:
    # Preserve readable line boundaries before removing tags.
    text = re.sub(r"</(div|p|br|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    return normalize_whitespace(text)


def clean_rtf_text(text: str) -> str:
    text = RTF_HEX_RE.sub("", text)
    text = RTF_CTRL_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ")
    return normalize_whitespace(text)


def clean_note_text(note_text: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    if "html" in ct:
        return clean_html_text(note_text)
    if "rtf" in ct:
        return clean_rtf_text(note_text)
    return normalize_whitespace(html.unescape(note_text))


def main():
    load_dotenv()

    raw_path = Path(os.getenv("RAW_NOTES_JSONL", "./data/raw/notes_raw.jsonl"))
    clean_path = Path(os.getenv("CLEAN_NOTES_JSONL", "./data/processed/notes_clean.jsonl"))
    clean_path.parent.mkdir(parents=True, exist_ok=True)

    if not raw_path.exists():
        raise FileNotFoundError(f"Raw notes file not found: {raw_path}")

    total = 0
    with raw_path.open("r", encoding="utf-8") as fin, clean_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            row = json.loads(line)
            raw_text = row.get("note_text", "")
            row["note_text_clean"] = clean_note_text(raw_text, row.get("content_type", ""))
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            total += 1

    print(f"Wrote {total} cleaned notes to {clean_path}")


if __name__ == "__main__":
    main()
