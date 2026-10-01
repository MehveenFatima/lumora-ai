import urllib.request
import json
import uuid
import sys
import fitz
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _api_auth  # noqa: E402,F401  (signs in and authenticates every API request)

BASE_URL = "http://localhost:3000"


def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"[FAIL] {msg}")
        sys.exit(1)
    print(f"  [OK] {msg}")


def test_create_empty_workspace():
    print("\n--- TEST 1: Empty Workspace Creation (Next.js Proxy -> FastAPI -> PostgreSQL) ---")
    url = f"{BASE_URL}/api/v1/workspaces"
    payload = {
        "name": "Production RAG Test (Empty)",
        "goal": "Verify pure empty workspace creation without attachments",
        "level": "intermediate",
        "target_date": "2026-12-31",
        "daily_target_minutes": 30,
        "description": "Deterministic workspace creation verification.",
        "icon_name": "FolderKanban",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        status = res.status
        body = json.loads(res.read().decode("utf-8"))

    assert_true(status == 201, f"POST /api/v1/workspaces returned HTTP {status}")
    ws_id = body.get("id")
    assert_true(bool(ws_id), f"Returned authoritative workspace ID: '{ws_id}'")
    assert_true(body.get("name") == payload["name"], "Returned correct workspace name")

    # Verify retrieval
    get_req = urllib.request.Request(f"{BASE_URL}/api/v1/workspaces/{ws_id}")
    with urllib.request.urlopen(get_req) as get_res:
        assert_true(get_res.status == 200, f"GET /api/v1/workspaces/{ws_id} returned HTTP 200")

    return ws_id


def test_create_workspace_with_pdf():
    print("\n--- TEST 2: Workspace Creation with Document Upload & Tutor Interaction ---")
    # Step 1: Create Workspace
    ws_url = f"{BASE_URL}/api/v1/workspaces"
    ws_payload = {
        "name": "SSL Security Track",
        "goal": "Master SSL/TLS Architecture",
        "level": "advanced",
    }
    req = urllib.request.Request(
        ws_url,
        data=json.dumps(ws_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        ws_body = json.loads(res.read().decode("utf-8"))
    ws_id = ws_body["id"]
    assert_true(bool(ws_id), f"Created workspace with ID: {ws_id}")

    # Step 2: Generate a valid multi-page PDF in memory using fitz
    pdf_doc = fitz.open()
    
    # Page 1
    p1 = pdf_doc.new_page()
    p1.insert_text(
        (50, 72),
        "SSL Unit 1 - Security Protocols Overview\n"
        "1. SSL Handshake Protocol: Establishes a secure session between client and server.\n"
        "2. SSL Record Protocol: Provides confidentiality and data integrity.\n"
        "3. Change Cipher Spec Protocol: Transitions connection into newly negotiated cryptographic parameters.\n"
        "4. Alert Protocol: Transmits error messages."
    )
    
    # Page 7
    for _ in range(5):
        pdf_doc.new_page()
    p7 = pdf_doc.new_page()
    p7.insert_text(
        (50, 72),
        "Page 7: Key Derivation\n"
        "Both client and server compute the 48-byte Master Secret from the Premaster Secret using pseudorandom function PRF."
    )
    
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    # Step 3: Upload Document via multipart/form-data
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    doc_url = f"{BASE_URL}/api/v1/workspaces/{ws_id}/documents"
    filename = "SSL-UNIT - 1 (1).pdf"
    
    parts = []
    parts.append(f"--{boundary}".encode())
    parts.append(f'Content-Disposition: form-data; name="title"'.encode())
    parts.append(b"")
    parts.append(b"SSL Unit 1 Notes")
    
    parts.append(f"--{boundary}".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    parts.append(b"Content-Type: application/pdf")
    parts.append(b"")
    parts.append(pdf_bytes)
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    
    body_data = b"\r\n".join(parts)
    
    doc_req = urllib.request.Request(
        doc_url,
        data=body_data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    
    with urllib.request.urlopen(doc_req) as doc_res:
        doc_status = doc_res.status
        doc_body = json.loads(doc_res.read().decode("utf-8"))
    
    assert_true(doc_status == 201, f"POST /api/v1/workspaces/{ws_id}/documents returned HTTP {doc_status}")
    doc_id = doc_body.get("id")
    assert_true(bool(doc_id), f"Document ingested with ID: {doc_id}")
    assert_true(doc_body.get("status") == "ready", f"Document status is '{doc_body.get('status')}'")
    assert_true(doc_body.get("chunk_count", 0) > 0, f"Generated {doc_body.get('chunk_count')} chunks in database")

    # Step 4: Ask Tutor through Next.js proxy
    tutor_url = f"{BASE_URL}/api/v1/workspaces/{ws_id}/tutor"
    tutor_payload = {
        "message": "What sources are currently in this workspace?",
    }
    tutor_req = urllib.request.Request(
        tutor_url,
        data=json.dumps(tutor_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(tutor_req) as tutor_res:
        tutor_status = tutor_res.status
        tutor_body = json.loads(tutor_res.read().decode("utf-8"))

    assert_true(tutor_status == 200, f"POST /api/v1/workspaces/{ws_id}/tutor returned HTTP 200")
    safe_content = tutor_body['message']['content'][:140].encode('ascii', 'replace').decode('ascii')
    print(f"  [OK] Tutor response: {safe_content}...")


if __name__ == "__main__":
    print("===============================================================")
    print("  LUMORAAI — E2E NEXT.JS PROXY & FASTAPI WORKSPACE CREATION TEST")
    print("===============================================================")
    test_create_empty_workspace()
    test_create_workspace_with_pdf()
    print("\n===============================================================")
    print("  ALL E2E PROXY & WORKSPACE CREATION TESTS PASSED!")
    print("===============================================================\n")
