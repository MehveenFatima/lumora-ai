import urllib.request
import json
import sys
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _api_auth  # noqa: E402,F401  (signs in and authenticates every API request)
DSA_WS = os.environ.get("LUMORA_DSA_WORKSPACE_ID", "dsa")  # id of a DSA workspace you own

BASE_URL = "http://localhost:3000"


def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"[FAIL] {msg}")
        sys.exit(1)
    print(f"  [OK] {msg}")


def test_dsa_presentation_seed():
    print("\n===============================================================")
    print("  LUMORAAI — DSA PRESENTATION DEMO SEED VERIFICATION")
    print("===============================================================\n")

    # 1. Verify DSA Workspace Metadata
    print("[STEP 1] Verifying DSA Workspace Metadata from PostgreSQL...")
    ws_req = urllib.request.Request(f"{BASE_URL}/api/v1/workspaces/{DSA_WS}")
    with urllib.request.urlopen(ws_req) as ws_res:
        assert_true(ws_res.status == 200, "GET /api/v1/workspaces/{DSA_WS} returned HTTP 200")
        ws = json.loads(ws_res.read().decode())
    
    assert_true(ws["id"] == "dsa", f"Workspace ID is '{ws['id']}'")
    assert_true(ws["name"] == "Data Structures & Algorithms", f"Workspace Name is '{ws['name']}'")
    assert_true(ws["overall_mastery"] == 74, f"Overall Mastery is {ws['overall_mastery']}%")
    assert_true(ws["document_count"] == 3, f"Document count is {ws['document_count']}")

    # 2. Verify Sources
    print("\n[STEP 2] Verifying Seeded OpenDSA Sources in DSA Workspace...")
    docs_req = urllib.request.Request(f"{BASE_URL}/api/v1/workspaces/{DSA_WS}/documents")
    with urllib.request.urlopen(docs_req) as docs_res:
        assert_true(docs_res.status == 200, "GET /api/v1/workspaces/{DSA_WS}/documents returned HTTP 200")
        docs_data = json.loads(docs_res.read().decode())
        docs = docs_data.get("documents", [])

    assert_true(len(docs) == 3, f"Found exactly 3 seeded OpenDSA documents (got: {len(docs)})")
    filenames = [d["filename"] for d in docs]
    assert_true("OpenDSA_DSA_Fundamentals.pdf" in filenames, "OpenDSA_DSA_Fundamentals.pdf exists")
    assert_true("OpenDSA_Algorithm_Analysis.pdf" in filenames, "OpenDSA_Algorithm_Analysis.pdf exists")
    assert_true("OpenDSA_Graph_Traversals.pdf" in filenames, "OpenDSA_Graph_Traversals.pdf exists")
    assert_true(all(d["status"] == "ready" for d in docs), "All documents have READY status")

    # 3. Real RAG AI Tutor Questions on DSA Sources
    print("\n[STEP 3] Testing Real RAG AI Tutor Grounded Answers on OpenDSA Sources...")
    
    # Q1: BFS vs DFS
    q1 = "What is the difference between BFS and DFS?"
    tutor_req1 = urllib.request.Request(
        f"{BASE_URL}/api/v1/workspaces/{DSA_WS}/tutor",
        data=json.dumps({"message": q1}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(tutor_req1) as res1:
        assert_true(res1.status == 200, "Tutor question 1 returned HTTP 200")
        ans1 = json.loads(res1.read().decode())
    
    assert_true(ans1["retrieval"]["grounded"] is True, "BFS vs DFS answer is grounded in OpenDSA sources")
    assert_true(len(ans1["citations"]) > 0, f"Produced {len(ans1['citations'])} citation(s)")
    assert_true(any("Graph" in c["document_name"] for c in ans1["citations"]), "Citation points to OpenDSA_Graph_Traversals.pdf")
    print(f"    Tutor Answer Preview: {ans1['message']['content'][:140]}...")

    # Q2: Binary Search Complexity
    q2 = "Explain why binary search is O(log n)."
    tutor_req2 = urllib.request.Request(
        f"{BASE_URL}/api/v1/workspaces/{DSA_WS}/tutor",
        data=json.dumps({"message": q2}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(tutor_req2) as res2:
        assert_true(res2.status == 200, "Tutor question 2 returned HTTP 200")
        ans2 = json.loads(res2.read().decode())
    
    assert_true(ans2["retrieval"]["grounded"] is True, "Binary Search answer is grounded")
    assert_true(len(ans2["citations"]) > 0, "Binary Search produced citations")
    assert_true(any("Algorithm" in c["document_name"] or "Analysis" in c["document_name"] for c in ans2["citations"]), "Citation points to OpenDSA_Algorithm_Analysis.pdf")
    print(f"    Tutor Answer Preview: {ans2['message']['content'][:140]}...")

    # Q3: Min-Heap Property
    q3 = "What is the key ordering property of a Min-Heap?"
    tutor_req3 = urllib.request.Request(
        f"{BASE_URL}/api/v1/workspaces/{DSA_WS}/tutor",
        data=json.dumps({"message": q3}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(tutor_req3) as res3:
        assert_true(res3.status == 200, "Tutor question 3 returned HTTP 200")
        ans3 = json.loads(res3.read().decode())
    
    assert_true(ans3["retrieval"]["grounded"] is True, "Min-Heap answer is grounded")
    assert_true(len(ans3["citations"]) > 0, "Min-Heap produced citations")

    # 4. Workspace Isolation Verification
    print("\n[STEP 4] Verifying Workspace Isolation Across Other Workspaces...")
    for other_ws in ["os", "ml", "aws"]:
        other_req = urllib.request.Request(f"{BASE_URL}/api/v1/workspaces/{other_ws}/documents")
        with urllib.request.urlopen(other_req) as other_res:
            other_docs = json.loads(other_res.read().decode()).get("documents", [])
            assert_true(len(other_docs) == 0, f"Workspace '{other_ws}' has 0 documents (Zero DSA leakage)")

    print("\n===============================================================")
    print("  🎉 ALL DSA PRESENTATION DEMO SEED VERIFICATIONS PASSED!")
    print("===============================================================\n")


if __name__ == "__main__":
    test_dsa_presentation_seed()
