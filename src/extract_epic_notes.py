#!/usr/bin/env python3
import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from pypdf import PdfReader


@dataclass
class EpicConfig:
    base_url: str
    token_url: str
    auth_method: str
    access_token: Optional[str]
    client_id: Optional[str]
    private_key_path: Optional[str]


class EpicFHIRClient:
    def __init__(self, cfg: EpicConfig):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        })
        self._token_expiry: Optional[datetime] = None

        if self.cfg.auth_method == "token" and self.cfg.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.cfg.access_token}"

    def _create_backend_jwt(self) -> str:
        import jwt
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        if not self.cfg.client_id or not self.cfg.private_key_path:
            raise ValueError("EPIC_CLIENT_ID and EPIC_PRIVATE_KEY_PATH are required for backend auth")

        with open(self.cfg.private_key_path, "rb") as f:
            private_key = load_pem_private_key(f.read(), None, default_backend())

        now = datetime.now(tz=timezone.utc)
        payload = {
            "iss": self.cfg.client_id,
            "sub": self.cfg.client_id,
            "aud": self.cfg.token_url,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=4)).timestamp()),
        }

        return jwt.encode(payload, private_key, algorithm="RS256", headers={"alg": "RS256", "typ": "JWT"})

    def _authenticate_backend_if_needed(self):
        if self.cfg.auth_method != "backend":
            return

        now = datetime.now(tz=timezone.utc)
        if self.session.headers.get("Authorization") and self._token_expiry and now < self._token_expiry:
            return

        client_assertion = self._create_backend_jwt()
        resp = requests.post(
            self.cfg.token_url,
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion,
            },
            timeout=30,
        )
        resp.raise_for_status()

        token_json = resp.json()
        access_token = token_json["access_token"]
        expires_in = int(token_json.get("expires_in", 3600))
        self._token_expiry = now + timedelta(seconds=expires_in - 30)
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def _get(self, path: str, params: Optional[Dict] = None, accept: Optional[str] = None) -> requests.Response:
        self._authenticate_backend_if_needed()
        headers = None
        if accept:
            headers = {"Accept": accept}
        resp = self.session.get(f"{self.cfg.base_url}{path}", params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp

    def get_clinical_notes_bundle(self, patient_id: str) -> Dict:
        resp = self._get("/DocumentReference", params={"patient": patient_id, "category": "clinical-note"})
        return resp.json()

    def get_document_reference(self, document_reference_id: str) -> Dict:
        resp = self._get(f"/DocumentReference/{document_reference_id}")
        return resp.json()

    def get_binary(self, binary_url_or_id: str) -> requests.Response:
        self._authenticate_backend_if_needed()
        if binary_url_or_id.startswith("http"):
            url = binary_url_or_id
        else:
            cleaned = binary_url_or_id.strip()
            if cleaned.startswith("Binary/"):
                url = f"{self.cfg.base_url}/{cleaned}"
            else:
                url = f"{self.cfg.base_url}/Binary/{cleaned}"
        resp = self.session.get(url, headers={"Accept": "application/pdf, text/plain, application/json, */*"}, timeout=60)
        resp.raise_for_status()
        return resp


def extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        import io

        reader = PdfReader(io.BytesIO(raw_bytes))
        chunks: List[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text.strip())
        return "\n".join(chunks)
    except Exception:
        return ""


def decode_text_from_response(content_type: str, raw_bytes: bytes) -> str:
    ct = (content_type or "").lower()

    if "text/plain" in ct:
        return raw_bytes.decode("utf-8", errors="ignore")

    if "json" in ct:
        try:
            payload = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
            if isinstance(payload, dict) and "data" in payload:
                return base64.b64decode(payload["data"]).decode("utf-8", errors="ignore")
            return json.dumps(payload)
        except Exception:
            return raw_bytes.decode("utf-8", errors="ignore")

    if "text/html" in ct or "text/rtf" in ct:
        return raw_bytes.decode("utf-8", errors="ignore")

    if "application/pdf" in ct or raw_bytes.startswith(b"%PDF"):
        return extract_pdf_text(raw_bytes)

    return ""


def iter_document_references(bundle: Dict) -> List[Dict]:
    out: List[Dict] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "DocumentReference":
            out.append(resource)
    return out


def build_note_record(patient_id: str, doc: Dict, attachment: Dict, text: str) -> Dict:
    doc_id = doc.get("id", "")
    note_date = doc.get("date", "")
    title = attachment.get("title") or doc.get("description") or ""
    content_type = attachment.get("contentType", "")
    source_url = attachment.get("url", "")

    return {
        "patient_id": patient_id,
        "document_reference_id": doc_id,
        "note_date": note_date,
        "title": title,
        "content_type": content_type,
        "source_url": source_url,
        "note_text": text.strip(),
    }


def get_patient_id_from_document_reference(doc: Dict) -> str:
    subject_ref = doc.get("subject", {}).get("reference", "")
    if subject_ref.startswith("Patient/"):
        return subject_ref.split("/", 1)[1]
    return ""


def main():
    load_dotenv()

    cfg = EpicConfig(
        base_url=os.getenv("EPIC_BASE_URL", "").rstrip("/"),
        token_url=os.getenv("EPIC_TOKEN_URL", ""),
        auth_method=os.getenv("EPIC_AUTH_METHOD", "open"),
        access_token=os.getenv("EPIC_ACCESS_TOKEN") or None,
        client_id=os.getenv("EPIC_CLIENT_ID") or None,
        private_key_path=os.getenv("EPIC_PRIVATE_KEY_PATH") or None,
    )

    patient_ids = [p.strip() for p in os.getenv("EPIC_PATIENT_IDS", "").split(",") if p.strip()]
    document_reference_ids = [
        d.strip() for d in os.getenv("DOCUMENT_REFERENCE_IDS", "").split(",") if d.strip()
    ]
    raw_path = Path(os.getenv("RAW_NOTES_JSONL", "./data/raw/notes_raw.jsonl"))
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    if not cfg.base_url:
        raise ValueError("EPIC_BASE_URL is required")
    if not patient_ids and not document_reference_ids:
        raise ValueError("Set EPIC_PATIENT_IDS and/or DOCUMENT_REFERENCE_IDS")

    client = EpicFHIRClient(cfg)

    written = 0
    with raw_path.open("w", encoding="utf-8") as f:
        # Path A: direct known DocumentReference IDs (works even when search-by-patient is forbidden).
        for doc_id in document_reference_ids:
            try:
                doc = client.get_document_reference(doc_id)
            except Exception as exc:
                print(f"Skipping DocumentReference {doc_id}: {exc}")
                continue

            patient_id = get_patient_id_from_document_reference(doc)
            for content in doc.get("content", []):
                attachment = content.get("attachment", {})
                url = attachment.get("url")
                if not url:
                    continue

                try:
                    resp = client.get_binary(url)
                    text = decode_text_from_response(resp.headers.get("Content-Type", ""), resp.content)
                    if not text.strip():
                        continue

                    row = build_note_record(patient_id, doc, attachment, text)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    written += 1
                except Exception as exc:
                    print(f"Skipping attachment for DocumentReference {doc_id}: {exc}")

        # Path B: search by patient ID (requires DocumentReference search access).
        for patient_id in patient_ids:
            try:
                bundle = client.get_clinical_notes_bundle(patient_id)
                docs = iter_document_references(bundle)
            except Exception as exc:
                print(f"Skipping patient {patient_id}: {exc}")
                continue

            for doc in docs:
                for content in doc.get("content", []):
                    attachment = content.get("attachment", {})
                    url = attachment.get("url")
                    if not url:
                        continue

                    try:
                        resp = client.get_binary(url)
                        text = decode_text_from_response(resp.headers.get("Content-Type", ""), resp.content)
                        if not text.strip():
                            continue

                        row = build_note_record(patient_id, doc, attachment, text)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        written += 1
                    except Exception as exc:
                        print(f"Skipping attachment for patient {patient_id}: {exc}")

    print(f"Wrote {written} extracted note records to {raw_path}")


if __name__ == "__main__":
    main()
