#!/usr/bin/env python3
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from dotenv import load_dotenv


def build_backend_token(client_id: str, private_key_path: str, token_url: str) -> Dict:
    with open(private_key_path, "rb") as f:
        private_key = load_pem_private_key(f.read(), None, default_backend())

    now = datetime.now(tz=timezone.utc)
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_url,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=4)).timestamp()),
    }
    assertion = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"alg": "RS256", "typ": "JWT"},
    )

    resp = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def call_and_report(name: str, url: str, headers: Dict, params: Dict = None) -> Dict:
    resp = requests.get(url, headers=headers, params=params, timeout=45)
    request_id = (
        resp.headers.get("x-request-id")
        or resp.headers.get("x-correlation-id")
        or resp.headers.get("x-amzn-requestid")
        or ""
    )

    body_text = resp.text
    operation_outcome = ""
    try:
        body_json = resp.json()
        if isinstance(body_json, dict) and body_json.get("resourceType") == "OperationOutcome":
            operation_outcome = json.dumps(body_json, indent=2)
        elif isinstance(body_json, dict):
            operation_outcome = json.dumps(
                {k: body_json.get(k) for k in ("resourceType", "id", "total") if k in body_json},
                indent=2,
            )
    except Exception:
        pass

    print("\n" + "=" * 80)
    print(f"Check: {name}")
    print(f"URL: {resp.url}")
    print(f"Status: {resp.status_code}")
    if request_id:
        print(f"Request ID: {request_id}")

    if operation_outcome:
        print("Body summary:")
        print(operation_outcome)
    else:
        print("Body (first 600 chars):")
        print(body_text[:600])

    return {
        "name": name,
        "status": resp.status_code,
        "url": resp.url,
        "request_id": request_id,
        "body_head": body_text[:600],
    }


def main():
    load_dotenv()

    base_url = (os.getenv("EPIC_BASE_URL") or "").rstrip("/")
    token_url = os.getenv("EPIC_TOKEN_URL") or ""
    auth_method = (os.getenv("EPIC_AUTH_METHOD") or "").strip().lower()
    client_id = os.getenv("EPIC_CLIENT_ID") or ""
    private_key_path = os.getenv("EPIC_PRIVATE_KEY_PATH") or ""
    access_token = os.getenv("EPIC_ACCESS_TOKEN") or ""
    patient_ids = [p.strip() for p in (os.getenv("EPIC_PATIENT_IDS") or "").split(",") if p.strip()]

    if not base_url:
        raise ValueError("Missing EPIC_BASE_URL")
    if not patient_ids:
        raise ValueError("Missing EPIC_PATIENT_IDS")

    print("Epic 403 Diagnostic")
    print("-" * 80)
    print(f"Base URL: {base_url}")
    print(f"Auth method: {auth_method}")
    print(f"Patients: {', '.join(patient_ids)}")

    if auth_method == "backend":
        if not client_id or not private_key_path or not token_url:
            raise ValueError("Backend mode requires EPIC_CLIENT_ID, EPIC_PRIVATE_KEY_PATH, EPIC_TOKEN_URL")
        token_json = build_backend_token(client_id, private_key_path, token_url)
        access_token = token_json["access_token"]
        print("\nToken acquired.")
        print(f"Granted scope: {token_json.get('scope', '(none returned)')}")
    elif auth_method == "token":
        if not access_token:
            raise ValueError("Token mode requires EPIC_ACCESS_TOKEN")
        print("\nUsing provided EPIC_ACCESS_TOKEN.")
    else:
        print("\nUsing open/no-auth mode. Most sandbox endpoints may return 401.")

    headers = {"Accept": "application/fhir+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    results: List[Dict] = []

    for pid in patient_ids:
        print("\n" + "#" * 80)
        print(f"Patient: {pid}")
        results.append(
            call_and_report(
                name="Patient.Read",
                url=f"{base_url}/Patient/{pid}",
                headers=headers,
            )
        )
        results.append(
            call_and_report(
                name="DocumentReference.Read (patient)",
                url=f"{base_url}/DocumentReference",
                headers=headers,
                params={"patient": pid},
            )
        )
        results.append(
            call_and_report(
                name="DocumentReference.Read (patient + category=clinical-note)",
                url=f"{base_url}/DocumentReference",
                headers=headers,
                params={"patient": pid, "category": "clinical-note"},
            )
        )

    print("\n" + "=" * 80)
    print("Summary")
    for row in results:
        print(f"- {row['name']}: {row['status']} ({row['url']})")

    forbidden = [r for r in results if r["status"] == 403]
    if forbidden:
        print("\n403 checks detected. Send Epic support/app owner:")
        print("1) Endpoint URL(s)")
        print("2) Status code(s)")
        print("3) Request ID(s) above")
        print("4) Granted scope from token response")
    else:
        print("\nNo 403 responses in this run.")


if __name__ == "__main__":
    main()
