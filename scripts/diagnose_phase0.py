import urllib.request
import urllib.error
import json
import uuid
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

FASTAPI_URL = "http://127.0.0.1:8000"
NEXTJS_URL = "http://localhost:3000"

def log_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_request(method, url, data=None, headers=None, multipart=False):
    headers = headers or {}
    body = None
    if data:
        if multipart:
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            parts = []
            for k, v in data.items():
                parts.append(f"--{boundary}".encode())
                if isinstance(v, tuple):
                    filename, content, content_type = v
                    parts.append(f'Content-Disposition: form-data; name="{k}"; filename="{filename}"'.encode())
                    parts.append(f'Content-Type: {content_type}'.encode())
                    parts.append(b"")
                    parts.append(content if isinstance(content, bytes) else content.encode("utf-8"))
                else:
                    parts.append(f'Content-Disposition: form-data; name="{k}"'.encode())
                    parts.append(b"")
                    parts.append(str(v).encode("utf-8"))
            parts.append(f"--{boundary}--".encode())
            parts.append(b"")
            body = b"\r\n".join(parts)
        else:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            elapsed = round((time.time() - start) * 1000, 2)
            res_body = res.read().decode("utf-8")
            try:
                parsed = json.loads(res_body)
            except Exception:
                parsed = res_body
            return {"status": res.status, "data": parsed, "elapsed_ms": elapsed, "error": None}
    except urllib.error.HTTPError as e:
        elapsed = round((time.time() - start) * 1000, 2)
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = err_body
        return {"status": e.code, "data": err_json, "elapsed_ms": elapsed, "error": f"HTTP {e.code}"}
    except Exception as e:
        elapsed = round((time.time() - start) * 1000, 2)
        return {"status": 0, "data": None, "elapsed_ms": elapsed, "error": str(e)}

def run_diagnostics():
    log_section("PHASE 0 DIAGNOSTICS: END-TO-END CONNECTIVITY TRACE")
    
    results = {}
    
    # 1. FastAPI Direct Health
    print("\n[1] Testing FastAPI Direct: GET http://127.0.0.1:8000/api/v1/health")
    fastapi_health = test_request("GET", f"{FASTAPI_URL}/api/v1/health")
    results["fastapi_health"] = fastapi_health
    if fastapi_health["status"] == 200:
        print(f"    ✓ SUCCESS (HTTP 200, {fastapi_health['elapsed_ms']}ms): {fastapi_health['data']}")
    else:
        print(f"    ❌ FAILED (Status: {fastapi_health['status']}, Error: {fastapi_health['error']})")
        print(f"    Diagnosis: FastAPI is either not running or blocked on port 8000.")

    # 2. Next.js Proxy Health
    print("\n[2] Testing Next.js Proxy: GET http://localhost:3000/api/v1/health")
    next_health = test_request("GET", f"{NEXTJS_URL}/api/v1/health")
    results["next_health"] = next_health
    if next_health["status"] == 200:
        print(f"    ✓ SUCCESS (HTTP 200, {next_health['elapsed_ms']}ms): {next_health['data']}")
    else:
        print(f"    ❌ FAILED (Status: {next_health['status']}, Error: {next_health['error']})")
        if next_health["status"] == 0:
            print("    Diagnosis: Next.js dev server is not responding on port 3000 (Frontend -> Proxy unreachable).")
        else:
            print("    Diagnosis: Proxy -> FastAPI rewrite failed or returned error.")

    # 3. Test POST /api/v1/workspaces (via Next.js Proxy)
    target_base = NEXTJS_URL if next_health["status"] == 200 else FASTAPI_URL
    print(f"\n[3] Testing Workspace Creation: POST {target_base}/api/v1/workspaces")
    ws_payload = {
        "name": "Diagnostic Test Track",
        "goal": "Verify Phase 0 Pipeline",
        "level": "intermediate",
        "target_date": "2026-12-31",
        "daily_target_minutes": 30,
        "description": "Diagnostic workspace",
        "icon_name": "FolderKanban"
    }
    ws_create = test_request("POST", f"{target_base}/api/v1/workspaces", data=ws_payload)
    results["workspace_create"] = ws_create
    ws_id = None
    if ws_create["status"] == 201:
        ws_id = ws_create["data"].get("id")
        print(f"    ✓ SUCCESS (HTTP 201, {ws_create['elapsed_ms']}ms): Created workspace ID: {ws_id}")
    else:
        print(f"    ❌ FAILED (Status: {ws_create['status']}, Error: {ws_create['error']}, Body: {ws_create['data']})")

    # 4. Test GET /api/v1/workspaces
    print(f"\n[4] Testing Workspace Listing: GET {target_base}/api/v1/workspaces")
    ws_list = test_request("GET", f"{target_base}/api/v1/workspaces")
    results["workspace_list"] = ws_list
    if ws_list["status"] == 200:
        count = len(ws_list["data"].get("workspaces", []))
        print(f"    ✓ SUCCESS (HTTP 200, {ws_list['elapsed_ms']}ms): Retrieved {count} workspaces")
    else:
        print(f"    ❌ FAILED (Status: {ws_list['status']}, Error: {ws_list['error']}, Body: {ws_list['data']})")

    # 5. Test Document Ingestion: POST /api/v1/workspaces/{id}/documents
    if ws_id:
        print(f"\n[5] Testing Document Ingestion: POST {target_base}/api/v1/workspaces/{ws_id}/documents")
        doc_data = {
            "title": "Diagnostic Note",
            "file": ("diagnostic.txt", "Breadth-First Search (BFS) is an unweighted shortest-path graph search algorithm using a FIFO queue.", "text/plain")
        }
        doc_upload = test_request("POST", f"{target_base}/api/v1/workspaces/{ws_id}/documents", data=doc_data, multipart=True)
        results["doc_upload"] = doc_upload
        if doc_upload["status"] == 201:
            print(f"    ✓ SUCCESS (HTTP 201, {doc_upload['elapsed_ms']}ms): Doc ID: {doc_upload['data'].get('id')}, Status: {doc_upload['data'].get('status')}")
        else:
            print(f"    ❌ FAILED (Status: {doc_upload['status']}, Error: {doc_upload['error']}, Body: {doc_upload['data']})")

        # 6. Test RAG Tutor: POST /api/v1/workspaces/{id}/tutor
        print(f"\n[6] Testing RAG Tutor: POST {target_base}/api/v1/workspaces/{ws_id}/tutor")
        tutor_data = {
            "message": "Why is BFS useful for shortest paths in an unweighted graph?"
        }
        tutor_res = test_request("POST", f"{target_base}/api/v1/workspaces/{ws_id}/tutor", data=tutor_data)
        results["tutor_res"] = tutor_res
        if tutor_res["status"] == 200:
            print(f"    ✓ SUCCESS (HTTP 200, {tutor_res['elapsed_ms']}ms)")
            print(f"    Answer: {tutor_res['data'].get('message', {}).get('content', '')[:100]}...")
            print(f"    Citations: {len(tutor_res['data'].get('citations', []))}")
        else:
            print(f"    ❌ FAILED (Status: {tutor_res['status']}, Error: {tutor_res['error']}, Body: {tutor_res['data']})")

    # 7. Root Cause Breakdown
    log_section("ROOT CAUSE & SUBSYSTEM DIAGNOSIS SUMMARY")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_diagnostics()
