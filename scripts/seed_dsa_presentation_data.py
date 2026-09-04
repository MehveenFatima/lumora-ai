import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import urllib.request
import json
import uuid
import fitz  # PyMuPDF

API_BASE = "http://127.0.0.1:8000/api/v1"
DSA_WORKSPACE_ID = "dsa"


def generate_dsa_fundamentals_pdf() -> bytes:
    doc = fitz.open()

    # Page 1: Overview & Linear Structures
    p1 = doc.new_page()
    p1.insert_text(
        (50, 60),
        "Data Structures & Algorithms Fundamentals — OpenDSA\n"
        "Official Reference: https://opendsa.cs.vt.edu/ODSA/Books/eu_book/html/index.html\n\n"
        "1. Abstract Data Types (ADTs) & Data Structures\n"
        "An Abstract Data Type defines the logical properties and operations of data independent of implementation.\n"
        "A Data Structure is the concrete physical representation in memory.\n\n"
        "2. Linear Data Structures: Arrays vs Linked Lists\n"
        "- Arrays allocate contiguous memory blocks providing O(1) random index access via base address + index * element_size.\n"
        "  Disadvantages include fixed capacity and O(n) worst-case insertion/deletion due to element shifting.\n"
        "- Linked Lists allocate individual nodes dynamically linked via pointers. Insertion and deletion at known node is O(1),\n"
        "  but random access is O(n) sequential traversal. Cache locality is significantly lower than arrays.\n\n"
        "3. Stacks (LIFO) and Queues (FIFO)\n"
        "- Stack: Last-In, First-Out abstract data type supporting push, pop, and peek in O(1) time. Applications include call stacks,\n"
        "  expression parsing, and DFS backtracking.\n"
        "- Queue: First-In, First-Out abstract data type supporting enqueue and dequeue in O(1) time. Applications include BFS graph\n"
        "  exploration, CPU task scheduling, and buffer management."
    )

    # Page 2: Trees & Binary Search Trees
    p2 = doc.new_page()
    p2.insert_text(
        (50, 60),
        "Trees & Binary Search Trees (BST) — OpenDSA\n\n"
        "1. Tree Terminology & Hierarchical Structures\n"
        "A tree is a non-linear hierarchical data structure consisting of nodes connected by directed edges.\n"
        "The root node has no parent; leaf nodes have no children. The height of a node is the length of the longest path to a leaf.\n\n"
        "2. Binary Search Tree (BST) Property\n"
        "For every node X in a Binary Search Tree:\n"
        "- All keys in the left subtree of X are strictly less than key(X).\n"
        "- All keys in the right subtree of X are strictly greater than key(X).\n"
        "- In-order traversal (Left, Root, Right) of a BST visits keys in strictly ascending sorted order.\n\n"
        "3. BST Complexity & Balancing\n"
        "- Balanced BST (e.g., AVL Tree, Red-Black Tree): Height is O(log n). Search, insertion, and deletion operate in O(log n) time.\n"
        "- Skewed BST (degenerate case): Height becomes O(n) when elements are inserted in already sorted order, causing tree operations\n"
        "  to degrade to O(n) linked list traversal."
    )

    # Page 3: Heaps & Priority Queues
    p3 = doc.new_page()
    p3.insert_text(
        (50, 60),
        "Heaps & Priority Queues — OpenDSA\n\n"
        "1. Binary Heap Definition & Properties\n"
        "A binary heap is a complete binary tree implemented efficiently as a contiguous array where for node at index i:\n"
        "- Left child is at index 2*i + 1 (0-indexed) or 2*i (1-indexed).\n"
        "- Right child is at index 2*i + 2 (0-indexed) or 2*i + 1 (1-indexed).\n"
        "- Parent is at index floor((i - 1) / 2).\n\n"
        "2. Heap Ordering Invariants\n"
        "- Min-Heap Property: For every node X, key(parent(X)) <= key(X). The minimum element is always at the root array[0].\n"
        "- Max-Heap Property: For every node X, key(parent(X)) >= key(X). The maximum element is always at the root array[0].\n"
        "Notice: Unlike BSTs, a binary heap does not maintain a total order between left and right sibling subtrees.\n\n"
        "3. Operations & Time Complexity\n"
        "- Insert (push): Add to end of array and sift-up (percolate up). Time complexity: O(log n).\n"
        "- Extract-Min / Extract-Max (pop): Replace root with last element and sift-down (percolate down). Time complexity: O(log n).\n"
        "- Build Heap (bottom-up heapify): Floyd's algorithm builds a heap from an arbitrary array in O(n) linear time."
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_algorithm_analysis_pdf() -> bytes:
    doc = fitz.open()

    # Page 1: Asymptotic Analysis & Big-O
    p1 = doc.new_page()
    p1.insert_text(
        (50, 60),
        "Algorithm Analysis & Complexity — OpenDSA\n"
        "Official Reference: https://opendsa.org/OpenDSA/Books/Catalog/html/AAIntro.html\n\n"
        "1. Asymptotic Notation Foundations\n"
        "Algorithm analysis quantifies the resource consumption (time and memory) of an algorithm as input size n grows asymptotically.\n"
        "- Big-O (O): Asymptotic upper bound. f(n) = O(g(n)) means f(n) <= c * g(n) for all n >= n0.\n"
        "- Big-Omega (Ω): Asymptotic lower bound. f(n) = Ω(g(n)) means f(n) >= c * g(n) for all n >= n0.\n"
        "- Big-Theta (Θ): Asymptotically tight bound. f(n) = Θ(g(n)) means c1 * g(n) <= f(n) <= c2 * g(n).\n\n"
        "2. Binary Search Logarithmic Complexity Proof\n"
        "Binary search operates on a sorted/monotonic array. At each iteration, the algorithm compares the target with the middle element\n"
        "and discards half of the search space. The recurrence relation is:\n"
        "  T(n) = T(n / 2) + O(1)\n"
        "Applying the Master Theorem (a=1, b=2, d=0) yields T(n) = Θ(log n). If the array is not sorted, binary search fails."
    )

    # Page 2: Sorting & Hash Tables
    p2 = doc.new_page()
    p2.insert_text(
        (50, 60),
        "Sorting Algorithms & Hashing Mechanisms — OpenDSA\n\n"
        "1. Comparison-Based Sorting Complexity\n"
        "- QuickSort: Average case O(n log n) with excellent cache locality. Worst-case is O(n^2) when the pivot repeatedly partitions\n"
        "  the array into highly unbalanced subarrays of sizes 0 and n - 1 (e.g. choosing first element on sorted array).\n"
        "- MergeSort: Stable divide-and-conquer sort with guaranteed Θ(n log n) time in best, average, and worst cases.\n"
        "  Requires O(n) auxiliary space for merging buffers.\n\n"
        "2. Hash Tables & Collision Resolution\n"
        "A hash table maps keys to array buckets via a hash function h(k).\n"
        "- Separate Chaining: Each bucket contains a linked list of collided entries. Average lookup is O(1) when load factor α is kept small.\n"
        "  Worst-case lookup degrades to O(n) if all keys hash to the identical bucket.\n"
        "- Open Addressing & Linear Probing: Collisions are resolved by probing sequential buckets (i + 1, i + 2, ...).\n"
        "  Susceptible to primary clustering where consecutive occupied slots merge into large blocks, degrading probe sequences."
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_graph_traversals_pdf() -> bytes:
    doc = fitz.open()

    # Page 1: Graph Representations & BFS vs DFS
    p1 = doc.new_page()
    p1.insert_text(
        (50, 60),
        "Graph Concepts & Traversals — OpenDSA\n"
        "Official Reference: https://opendsa.org/OpenDSA/Books/Catalog/html/GraphIntro.html\n\n"
        "1. Graph Representations\n"
        "- Adjacency Matrix: 2D array of size V x V where matrix[u][v] = 1 if an edge exists. Space complexity is O(V^2).\n"
        "  Edge existence query is O(1), but finding all neighbors of a vertex requires O(V) time.\n"
        "- Adjacency List: Array of V lists where list[u] stores all adjacent neighbors of u. Space complexity is O(V + E),\n"
        "  making it memory-optimal for sparse graphs where E << V^2.\n\n"
        "2. Breadth-First Search (BFS) vs Depth-First Search (DFS)\n"
        "- Breadth-First Search (BFS):\n"
        "  * Uses a FIFO Queue to visit vertices level by level.\n"
        "  * Traversal Order: Visits all immediate neighbors at distance d before moving to distance d + 1.\n"
        "  * Application: Computes the shortest path (minimum number of edges) on unweighted graphs.\n"
        "  * Time Complexity: O(V + E) with adjacency list; Space Complexity: O(V) for queue and visited set.\n\n"
        "- Depth-First Search (DFS):\n"
        "  * Uses a LIFO Stack or recursion to explore as deep as possible along each branch before backtracking.\n"
        "  * Traversal Order: Traverses deeply down one path until a dead end or visited node is reached, then backtracks.\n"
        "  * Application: Cycle detection in directed graphs (via back-edge classification), topological sorting on DAGs,\n"
        "    and finding strongly connected components (Kosaraju / Tarjan).\n"
        "  * Time Complexity: O(V + E) with adjacency list; Space Complexity: O(V) recursion call stack depth in worst case."
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def upload_document_to_api(workspace_id: str, title: str, filename: str, pdf_bytes: bytes):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    url = f"{API_BASE}/workspaces/{workspace_id}/documents"

    parts = []
    parts.append(f"--{boundary}".encode())
    parts.append(b'Content-Disposition: form-data; name="title"')
    parts.append(b"")
    parts.append(title.encode("utf-8"))

    parts.append(f"--{boundary}".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    parts.append(b"Content-Type: application/pdf")
    parts.append(b"")
    parts.append(pdf_bytes)
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")

    body_data = b"\r\n".join(parts)

    req = urllib.request.Request(
        url,
        data=body_data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    with urllib.request.urlopen(req) as res:
        status = res.status
        body = json.loads(res.read().decode("utf-8"))
        return status, body


def seed_dsa():
    print("\n===============================================================")
    print("  LUMORAAI — SEEDING DSA WORKSPACE DEMONSTRATION DATASET")
    print("===============================================================\n")

    # 1. Verify DSA workspace exists in backend
    try:
        ws_res = urllib.request.urlopen(f"{API_BASE}/workspaces/{DSA_WORKSPACE_ID}")
        dsa_ws = json.loads(ws_res.read().decode())
    except Exception as e:
        print(f"❌ ERROR: DSA workspace '{DSA_WORKSPACE_ID}' not found on backend: {e}")
        sys.exit(1)

    print(f"✓ Found target DSA workspace: '{dsa_ws['name']}' (ID: {DSA_WORKSPACE_ID})")

    # 2. Delete existing documents in DSA workspace to prevent duplicates
    try:
        docs_res = urllib.request.urlopen(f"{API_BASE}/workspaces/{DSA_WORKSPACE_ID}/documents")
        existing_docs = json.loads(docs_res.read().decode()).get("documents", [])
        for doc in existing_docs:
            if doc["filename"].startswith("OpenDSA_"):
                del_req = urllib.request.Request(f"{API_BASE}/documents/{doc['id']}", method="DELETE")
                urllib.request.urlopen(del_req)
                print(f"  ✓ Cleaned existing doc: {doc['filename']}")
    except Exception as e:
        print(f"Notice during cleanup: {e}")

    # 3. Prepare OpenDSA Sources
    sources = [
        {
            "title": "Data Structures & Algorithms — OpenDSA",
            "filename": "OpenDSA_DSA_Fundamentals.pdf",
            "bytes_func": generate_dsa_fundamentals_pdf,
        },
        {
            "title": "Algorithm Analysis & Complexity — OpenDSA",
            "filename": "OpenDSA_Algorithm_Analysis.pdf",
            "bytes_func": generate_algorithm_analysis_pdf,
        },
        {
            "title": "Graph Concepts & Traversals — OpenDSA",
            "filename": "OpenDSA_Graph_Traversals.pdf",
            "bytes_func": generate_graph_traversals_pdf,
        },
    ]

    # 4. Upload each document to the live FastAPI backend
    for src in sources:
        pdf_bytes = src["bytes_func"]()
        st, body = upload_document_to_api(DSA_WORKSPACE_ID, src["title"], src["filename"], pdf_bytes)
        print(f"  ✓ Uploaded '{src['filename']}' (ID: {body['id']}, Status: {body['status']}, Chunks: {body.get('chunk_count', 0)})")

    print(f"\n🎉 Successfully seeded {len(sources)} OpenDSA source documents into live backend for '{DSA_WORKSPACE_ID}'!\n")


if __name__ == "__main__":
    seed_dsa()
