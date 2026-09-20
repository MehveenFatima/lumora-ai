"""
LumoraAI - Presentation Seeding Script
Populates the authoritative presentation demonstration environment:
1. Phase 0 Health Check (:8000 direct and :3000 proxy)
2. Rule 3 Exact Name Lookup for the 4 presentation workspaces
3. Generates 12 clean multi-page demonstration PDFs via PyMuPDF (fitz)
4. Uploads and indexes documents into each workspace via FastAPI /api/v1
5. Seeds BKT mastery, topic mastery, and knowledge gaps for presentation-demo-user & default_user
6. Generates flashcards, study plans, and activities
Idempotent and safe to run multiple times.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List

import httpx
import pymupdf  # PyMuPDF

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FASTAPI_URL = "http://127.0.0.1:8000"
PROXY_URL = "http://localhost:3000"

DEMO_USERS = ["default_user", "presentation-demo-user"]

SUBJECTS_CONFIG = [
    {
        "name": "Data Structures & Algorithms",
        "description": "Comprehensive study of linear structures, balanced search trees, heaps, and graph algorithms.",
        "goal": "Master technical interview data structures and algorithmic complexity analysis",
        "level": "intermediate",
        "icon_name": "Layers",
        "docs": [
            {
                "filename": "OpenDSA_DSA_Fundamentals.pdf",
                "title": "OpenDSA - Data Structures Fundamentals",
                "pages": [
                    (
                        "Linear Data Structures: Arrays and Memory Representation",
                        "Arrays provide contiguous memory allocation where each element can be accessed in O(1) time using index calculation: Address(A[i]) = BaseAddress + i * sizeof(Element). "
                        "Because elements are stored contiguously in cache lines, arrays exhibit exceptional spatial locality of reference, minimizing CPU cache misses during sequential iteration.\n\n"
                        "Dynamic arrays (such as Python lists or C++ std::vector) allocate extra capacity upon initialization. When current capacity is exceeded, the dynamic array allocates a new memory block "
                        "with double the previous capacity, copies all existing elements over, and deallocates the old memory. While this reallocation requires O(n) time, amortized analysis proves that across n insertions, "
                        "the aggregate cost is O(n), yielding an O(1) amortized insertion runtime."
                    ),
                    (
                        "Linked Lists: Singly vs Doubly Linked Structures",
                        "Linked lists store discrete node structures connected via pointer references. Each node in a singly linked list contains data and a next pointer, requiring pointer memory overhead. "
                        "Doubly linked lists store both next and prev pointers, allowing bidirectional traversal at the cost of additional memory per node.\n\n"
                        "Advantages: Insertions and deletions at the head or known positions execute in O(1) time without contiguous memory reallocation. Disadvantages: Direct indexing requires O(n) sequential traversal, "
                        "and scattered node memory locations cause frequent CPU cache line invalidations compared to contiguous arrays."
                    ),
                    (
                        "Stacks, Queues, and Asymptotic Complexity Analysis",
                        "Stacks enforce Last-In, First-Out (LIFO) semantics with push and pop operations executing in O(1) time. Stacks govern procedure call execution frames, recursive backtracking, and syntax tree parsing.\n\n"
                        "Queues enforce First-In, First-Out (FIFO) semantics, utilized in task scheduling, asynchronous message buffers, and Breadth-First Search (BFS). Circular ring buffers avoid O(n) element shifting during dequeue.\n\n"
                        "Asymptotic Notation: Big-O represents the upper bound asymptotic complexity, Big-Omega represents the lower bound, and Big-Theta represents a tight bound where f(n) is bounded above and below by constants c1*g(n) and c2*g(n)."
                    ),
                ]
            },
            {
                "filename": "OpenDSA_Trees_Heaps.pdf",
                "title": "OpenDSA - Balanced Trees and Binary Heaps",
                "pages": [
                    (
                        "Binary Search Trees (BST) Mechanics and Degradation",
                        "A Binary Search Tree satisfies the invariant that for any node X, all keys in the left subtree are strictly less than X.key, and all keys in the right subtree are strictly greater than X.key. "
                        "In an ideal balanced tree of height h = floor(log2(n)), search, insert, and delete take O(log n) time. However, inserting pre-sorted keys causes the BST to degenerate into an O(n) linear linked list."
                    ),
                    (
                        "Self-Balancing AVL Trees and Rotation Invariants",
                        "An AVL tree guarantees an O(log n) worst-case height by enforcing that for every node, the Balance Factor (BF = height(LeftSubtree) - height(RightSubtree)) is strictly in {-1, 0, 1}.\n\n"
                        "When an insertion causes BF to become +2 or -2, tree rotations restore balance:\n"
                        "1. Left-Left (LL) Heavy: Fixed via a single Right Rotation.\n"
                        "2. Right-Right (RR) Heavy: Fixed via a single Left Rotation.\n"
                        "3. Left-Right (LR) Heavy: Fixed via a Double Rotation: Left rotate on left child, followed by Right rotate on unbalanced root.\n"
                        "4. Right-Left (RL) Heavy: Fixed via a Double Rotation: Right rotate on right child, followed by Left rotate on unbalanced root."
                    ),
                    (
                        "Binary Heaps and Priority Queue Operations",
                        "A Binary Heap is a complete binary tree satisfying the Heap Property. In a Min-Heap, parent.key <= child.key for all nodes. Arrays efficiently represent binary heaps without pointers: for node index i, left_child = 2i + 1, right_child = 2i + 2, and parent = floor((i - 1) / 2).\n\n"
                        "Insertion (heappush): Append element to end of array and bubble-up (sift-up) in O(log n) time. Extraction (heappop): Replace root with last element and bubble-down (sift-down) in O(log n) time. "
                        "Floyd's Heapify builds a valid heap in-place in O(n) linear time by sifting down nodes from floor(n/2) down to 0."
                    ),
                ]
            },
            {
                "filename": "OpenDSA_Graph_Traversals.pdf",
                "title": "OpenDSA - Graph Traversals and Shortest Paths",
                "pages": [
                    (
                        "Graph Representation Models: Matrix vs Adjacency List",
                        "Graphs G = (V, E) can be represented as an Adjacency Matrix or Adjacency List.\n\n"
                        "Adjacency Matrix: A V x V 2D boolean or weight matrix where Matrix[u][v] denotes the edge between u and v. Lookup of edge existence takes O(1) time, but memory footprint is O(V^2), making it prohibitive for sparse graphs.\n\n"
                        "Adjacency List: An array or dictionary of lists where List[u] stores all adjacent vertices to u. Memory is O(V + E). Finding all neighbors of vertex u takes O(deg(u)) time, which is optimal for sparse graph traversal."
                    ),
                    (
                        "Breadth-First Search (BFS) and Depth-First Search (DFS)",
                        "Breadth-First Search (BFS) explores vertices level by level using a FIFO queue. In an unweighted graph, BFS discovers the minimum edge-count path from source s to target t in O(V + E) time.\n\n"
                        "Depth-First Search (DFS) explores as deep as possible along each branch using recursion or a LIFO stack. DFS assigns discovery and finishing timestamps used for Topological Sorting and Strongly Connected Components (Kosaraju or Tarjan). In directed graphs, back edges identify cycles."
                    ),
                    (
                        "Dijkstra's Algorithm and Min-Heap Priority Queues",
                        "Dijkstra's algorithm calculates the shortest path from a single source to all vertices in a weighted graph with non-negative edge weights.\n\n"
                        "Algorithm steps:\n"
                        "1. Initialize dist[source] = 0 and dist[v] = infinity for all other vertices.\n"
                        "2. Insert (dist[source], source) into a Min-Heap Priority Queue.\n"
                        "3. While priority queue is non-empty, extract vertex u with minimum tentative distance.\n"
                        "4. For each neighbor v with edge weight w(u, v): if dist[u] + w(u, v) < dist[v], update dist[v] = dist[u] + w(u, v) and push (dist[v], v) into the min-heap.\n"
                        "Using a binary min-heap, Dijkstra's algorithm executes in O((V + E) log V) time."
                    ),
                ]
            },
        ],
        "mastery_seed": [
            {"concept": "Arrays", "topic": "Linear Data Structures", "p_mastery": 0.92, "is_correct": True, "attempts": 8, "correct": 8},
            {"concept": "Linked Lists", "topic": "Linear Data Structures", "p_mastery": 0.88, "is_correct": True, "attempts": 7, "correct": 6},
            {"concept": "Binary Search Trees", "topic": "Trees & Hierarchical Structures", "p_mastery": 0.65, "is_correct": True, "attempts": 5, "correct": 3},
            {"concept": "AVL Tree Rotations", "topic": "Trees & Hierarchical Structures", "p_mastery": 0.35, "is_correct": False, "attempts": 5, "correct": 1, "gap_priority": 0.82, "status": "critical_gap", "action": "targeted_practice", "reason": "Repeated errors on left-right double rotations."},
            {"concept": "Graph Traversals (Dijkstra)", "topic": "Graph Algorithms", "p_mastery": 0.30, "is_correct": False, "attempts": 6, "correct": 1, "gap_priority": 0.88, "status": "critical_gap", "action": "targeted_practice", "reason": "Difficulty maintaining min-heap invariant during edge relaxation."},
        ]
    },
    {
        "name": "Operating Systems",
        "description": "In-depth exploration of processes, concurrency, CPU scheduling, virtual memory, and paging.",
        "goal": "Master kernel mechanics, synchronization primitives, and memory management",
        "level": "intermediate",
        "icon_name": "Cpu",
        "docs": [
            {
                "filename": "OS_Processes_Threads.pdf",
                "title": "Operating Systems - Processes and Concurrency",
                "pages": [
                    (
                        "Process Concept, Memory Layout, and PCB",
                        "A process is a program in execution. The memory layout of an active process consists of:\n"
                        "1. Text Segment: Compiled executable machine instructions.\n"
                        "2. Data & BSS Segments: Initialized and uninitialized global variables.\n"
                        "3. Heap: Dynamically allocated memory expanding upwards (malloc / new).\n"
                        "4. Stack: Local variables, return addresses, and activation records expanding downwards.\n\n"
                        "The Operating System maintains a Process Control Block (PCB) for each process containing: Process ID (PID), program counter, CPU registers, process state, CPU scheduling information, memory management tables, and open file descriptors."
                    ),
                    (
                        "Process State Transitions and Context Switching",
                        "A process transitions through lifecycle states: New -> Ready -> Running -> Waiting (Blocked) -> Terminated.\n\n"
                        "A Context Switch occurs when the CPU scheduler switches execution from process P1 to process P2:\n"
                        "1. The kernel saves P1's CPU state, registers, and program counter into P1's PCB.\n"
                        "2. The kernel loads P2's context from P2's PCB into hardware CPU registers.\n"
                        "3. Context switching incurs direct latency (register saving) and indirect latency (cache line invalidation and TLB flushing)."
                    ),
                    (
                        "Threads, Concurrency, and Race Conditions",
                        "A thread is a basic unit of CPU utilization comprising a thread ID, program counter, register set, and stack. Multiple threads within the same process share the Text, Data, Heap, and file resources.\n\n"
                        "A Race Condition occurs when multiple threads concurrently access shared memory and the final result depends on the non-deterministic interleaving of instructions.\n"
                        "Critical Section Problem requires three conditions: Mutual Exclusion (only one thread in critical section), Progress (selection of waiting threads cannot be postponed indefinitely), and Bounded Waiting (a limit exists on attempts before entry)."
                    ),
                ]
            },
            {
                "filename": "OS_CPU_Scheduling.pdf",
                "title": "Operating Systems - CPU Scheduling Disciplines",
                "pages": [
                    (
                        "Scheduling Criteria and Metrics",
                        "The CPU scheduler selects a process from the Ready queue and allocates CPU cycles. Performance metrics include:\n"
                        "1. CPU Utilization: Percentage of time CPU is executing user or system processes.\n"
                        "2. Throughput: Number of processes completed per unit time.\n"
                        "3. Turnaround Time: Total elapsed time from submission to process completion.\n"
                        "4. Waiting Time: Aggregate time spent waiting in the Ready queue.\n"
                        "5. Response Time: Time from request submission to first output response."
                    ),
                    (
                        "First-Come First-Served (FCFS) and Shortest Job First (SJF)",
                        "FCFS is non-preemptive: processes are assigned CPU in arrival order. A long CPU-bound process arriving before short I/O-bound processes leads to the Convoy Effect, drastically inflating average waiting time.\n\n"
                        "SJF associates each process with the length of its next CPU burst. Provably optimal in minimizing average waiting time. Preemptive SJF is known as Shortest Remaining Time First (SRTF)."
                    ),
                    (
                        "Round Robin (RR) and Priority Inversion",
                        "Round Robin assigns each process a fixed time quantum q. If a process does not complete within q, it is preempted and returned to the tail of the Ready queue. If q is excessively large, RR degenerates into FCFS; if q is too small, context switch overhead dominates CPU execution.\n\n"
                        "Priority Inversion occurs when a lower-priority process holds a mutual exclusion lock required by a higher-priority process, while an intermediate-priority process preempts the lower-priority one. Solved using Priority Inheritance Protocol."
                    ),
                ]
            },
            {
                "filename": "OS_Virtual_Memory_Paging.pdf",
                "title": "Operating Systems - Virtual Memory and Paging",
                "pages": [
                    (
                        "Virtual Memory, Paging Architecture, and Page Tables",
                        "Virtual Memory decouples user logical memory from physical memory, allowing execution of processes that exceed available physical RAM. Paging divides logical address space into fixed-size Pages and physical RAM into Page Frames of identical size (typically 4 KB).\n\n"
                        "Address Translation: The CPU generates a logical address containing Page Number (p) and Offset (d). The Memory Management Unit (MMU) uses p as an index into the Page Table to retrieve Frame Number (f). Physical Address = (f * PageSize) + d. Page Table Entries contain valid/invalid bits indicating presence in RAM."
                    ),
                    (
                        "Translation Lookaside Buffer (TLB) and Page Faults",
                        "To avoid two memory accesses per address translation (one for the page table, one for physical data), hardware provides a Translation Lookaside Buffer (TLB)—a fast associative cache. Effective Memory Access Time (EMAT) = HitRate * (TLBAccess + MemAccess) + (1 - HitRate) * (TLBAccess + 2*MemAccess).\n\n"
                        "When a process accesses a page with valid bit = 0, a Page Fault trap is generated:\n"
                        "1. OS traps to kernel and checks if address was legitimate.\n"
                        "2. OS finds a free physical page frame (or evicts an existing page).\n"
                        "3. Disk controller initiates I/O to fetch page contents into frame.\n"
                        "4. Page table is updated with frame number and valid bit = 1.\n"
                        "5. Instruction causing the page fault is restarted."
                    ),
                    (
                        "Page Replacement Algorithms: FIFO, LRU, and Clock",
                        "When physical RAM is exhausted, page replacement algorithms choose a victim frame to swap out to disk:\n"
                        "1. FIFO: Replaces the oldest page. Suffers from Belady's Anomaly (allocating more frames can paradoxically increase page faults).\n"
                        "2. Optimal (OPT): Replaces the page that will not be used for the longest future time. Used as an unattainable theoretical benchmark.\n"
                        "3. Least Recently Used (LRU): Replaces the page that has not been referenced for the longest past interval. Free from Belady's Anomaly.\n"
                        "4. Clock Algorithm (Second Chance): Uses a circular buffer and a reference bit. If bit is 1, it resets bit to 0 and advances hand; if bit is 0, it selects that frame for replacement."
                    ),
                ]
            },
        ],
        "mastery_seed": [
            {"concept": "CPU Scheduling", "topic": "Processor Management", "p_mastery": 0.90, "is_correct": True, "attempts": 8, "correct": 7},
            {"concept": "Processes & Threads", "topic": "Process Lifecycle", "p_mastery": 0.86, "is_correct": True, "attempts": 6, "correct": 5},
            {"concept": "Race Conditions & Synchronization", "topic": "Concurrency & Synchronization", "p_mastery": 0.38, "is_correct": False, "attempts": 5, "correct": 2, "gap_priority": 0.78, "status": "needs_review", "action": "targeted_practice", "reason": "Confusion between mutex locks and binary semaphores."},
            {"concept": "Virtual Memory Page Replacement (LRU/Clock)", "topic": "Memory Management", "p_mastery": 0.32, "is_correct": False, "attempts": 7, "correct": 2, "gap_priority": 0.85, "status": "critical_gap", "action": "targeted_practice", "reason": "Frequent misses on second-chance clock bit resetting."},
        ]
    },
    {
        "name": "DBMS",
        "description": "Relational database concepts, SQL querying, schema normalization, ACID transactions, and indexing.",
        "goal": "Design normalized database architectures and optimize transaction throughput",
        "level": "intermediate",
        "icon_name": "Database",
        "docs": [
            {
                "filename": "DBMS_SQL_Keys.pdf",
                "title": "Database Systems - Relational Model and SQL",
                "pages": [
                    (
                        "Relational Model Concepts and Integrity Constraints",
                        "In relational databases, data is organized into Relations (tables), Tuples (rows), and Attributes (columns). Each attribute has a defined Domain of valid atomic values.\n\n"
                        "Relational Integrity Constraints guarantee data validity:\n"
                        "1. Entity Integrity: Primary key values cannot be NULL, ensuring each tuple is uniquely identifiable.\n"
                        "2. Referential Integrity: A foreign key in a referencing relation must either match a valid primary key in the referenced relation or be completely NULL.\n"
                        "3. Domain Integrity: Attribute values must conform to defined data types, formats, and check constraints."
                    ),
                    (
                        "Keys Classification and Relational Algebra",
                        "Keys enforce relational uniqueness and relationship integrity:\n"
                        "1. Super Key: Any set of attributes that uniquely identifies a tuple within a relation.\n"
                        "2. Candidate Key: A minimal super key (no proper subset is a super key).\n"
                        "3. Primary Key: The chosen candidate key used by the database system as the primary tuple identifier.\n"
                        "4. Alternate Key: Candidate keys not chosen as the primary key.\n"
                        "5. Foreign Key: An attribute referencing the primary key of another relation."
                    ),
                    (
                        "SQL Operations and Join Execution Mechanics",
                        "SQL categorizes operations into Data Definition Language (DDL: CREATE, ALTER, DROP) and Data Manipulation Language (DML: SELECT, INSERT, UPDATE, DELETE).\n\n"
                        "Join Operations combine rows from two relations based on predicate evaluation:\n"
                        "- Inner Join: Returns rows with matching keys in both relations.\n"
                        "- Left Outer Join: Returns all rows from the left relation, padding unmatched right attributes with NULL.\n"
                        "- Right / Full Outer Join: Preserves unmatched rows from right or both relations.\n"
                        "- Cross Join: Computes Cartesian product (size |R| * |S|)."
                    ),
                ]
            },
            {
                "filename": "DBMS_Normalization.pdf",
                "title": "Database Systems - Functional Dependencies and Normal Forms",
                "pages": [
                    (
                        "Functional Dependencies and Armstrong's Axioms",
                        "A Functional Dependency (FD) X -> Y states that if two tuples agree on attributes X, they must agree on attributes Y. X is called the Determinant.\n\n"
                        "Armstrong's Axioms are sound and complete inference rules for FDs:\n"
                        "1. Reflexivity: If Y is a subset of X, then X -> Y.\n"
                        "2. Augmentation: If X -> Y, then XZ -> YZ for any set of attributes Z.\n"
                        "3. Transitivity: If X -> Y and Y -> Z, then X -> Z.\n"
                        "Derived rules include Union (X -> Y and X -> Z implies X -> YZ) and Decomposition (X -> YZ implies X -> Y and X -> Z)."
                    ),
                    (
                        "First (1NF), Second (2NF), and Third (3NF) Normal Forms",
                        "Normalization eliminates insertion, update, and deletion anomalies caused by data redundancy.\n\n"
                        "1NF: All attribute values must be atomic (no repeating groups, arrays, or nested tables).\n\n"
                        "2NF: Relation is in 1NF and every non-prime attribute is fully functionally dependent on every candidate key (no Partial Dependencies where a non-prime depends on a proper subset of a composite candidate key).\n\n"
                        "3NF: Relation is in 2NF and no non-prime attribute is transitively dependent on a candidate key (for every non-trivial FD X -> Y, either X is a super key or Y is a prime attribute)."
                    ),
                    (
                        "Boyce-Codd Normal Form (BCNF) and Decomposition Criteria",
                        "A relation is in BCNF if for every non-trivial functional dependency X -> Y, X must be a Super Key. BCNF is strictly stronger than 3NF because it prohibits non-super key determinants even if Y is a prime attribute.\n\n"
                        "Decomposition Requirements:\n"
                        "1. Lossless-Join Decomposition: Decomposing R into R1 and R2 must satisfy that R1 intersect R2 -> R1 or R1 intersect R2 -> R2, guaranteeing no spurious tuples upon natural join.\n"
                        "2. Dependency Preservation: The union of functional dependencies in decomposed relations must logically imply all original dependencies in F+."
                    ),
                ]
            },
            {
                "filename": "DBMS_Transactions_Indexing.pdf",
                "title": "Database Systems - Transactions and Indexing",
                "pages": [
                    (
                        "Transaction Management and ACID Properties",
                        "A transaction is a logical unit of database processing executing multiple read and write operations. ACID properties ensure database reliability:\n"
                        "1. Atomicity: All operations complete successfully, or all changes are rolled back (All-or-Nothing).\n"
                        "2. Consistency: Execution in isolation preserves database integrity constraints.\n"
                        "3. Isolation: Intermediate transaction states are invisible to concurrently executing transactions.\n"
                        "4. Durability: Once committed, state changes survive system crashes or power failures via write-ahead logging (WAL)."
                    ),
                    (
                        "Concurrency Anomalies and Two-Phase Locking (2PL)",
                        "Uncontrolled concurrent executions introduce anomalies: Dirty Read (reading uncommitted data), Non-Repeatable Read (rereading a value modified by another committed transaction), and Phantom Read (rereading a range where new matching rows were inserted).\n\n"
                        "Two-Phase Locking (2PL) guarantees conflict serializability:\n"
                        "1. Growing Phase: Transaction may acquire locks (Shared S-locks or Exclusive X-locks) but cannot release any lock.\n"
                        "2. Shrinking Phase: Transaction may release locks but cannot acquire new locks.\n"
                        "Strict 2PL holds all exclusive locks until commit or abort, preventing cascading rollbacks."
                    ),
                    (
                        "B-Tree and B+ Tree Index Architectures",
                        "Indexes accelerate data retrieval without full table scans. A B+ Tree is a self-balancing search tree where:\n"
                        "1. Internal nodes store only search keys and child pointers, maximizing node fan-out and minimizing tree height (typically 3-4 levels for billions of rows).\n"
                        "2. Leaf nodes store actual data pointers (or full rows in Clustered Indexes) and are linked in a contiguous doubly linked list, enabling O(log n) point lookups and efficient sequential range scans."
                    ),
                ]
            },
        ],
        "mastery_seed": [
            {"concept": "SQL & Keys", "topic": "Relational Foundations", "p_mastery": 0.92, "is_correct": True, "attempts": 9, "correct": 8},
            {"concept": "ACID Transactions", "topic": "Transaction Management", "p_mastery": 0.68, "is_correct": True, "attempts": 5, "correct": 3},
            {"concept": "Indexing & B-Trees", "topic": "Physical Storage", "p_mastery": 0.70, "is_correct": True, "attempts": 6, "correct": 4},
            {"concept": "BCNF Normalization", "topic": "Schema Normalization", "p_mastery": 0.34, "is_correct": False, "attempts": 6, "correct": 2, "gap_priority": 0.86, "status": "critical_gap", "action": "targeted_practice", "reason": "Difficulty decomposing relations without losing functional dependencies."},
        ]
    },
    {
        "name": "Machine Learning",
        "description": "Supervised and unsupervised learning, regression, classification metrics, tree ensembles, and validation.",
        "goal": "Build robust predictive models and prevent overfitting in production pipelines",
        "level": "intermediate",
        "icon_name": "Brain",
        "docs": [
            {
                "filename": "ML_Regression_Fundamentals.pdf",
                "title": "Machine Learning - Linear Regression and Optimization",
                "pages": [
                    (
                        "Supervised Learning Framework and Linear Regression",
                        "In supervised learning, algorithms learn a mapping function f: X -> y from labeled training pairs (x_i, y_i). In linear regression, the model predicts target y_hat = theta_0 + theta_1 * x_1 + ... + theta_p * x_p.\n\n"
                        "Cost Function: The performance is evaluated using Mean Squared Error (MSE): J(theta) = (1 / 2m) * sum((h_theta(x_i) - y_i)^2). Because MSE is a convex quadratic function, it possesses a single global minimum."
                    ),
                    (
                        "Gradient Descent and Analytical Normal Equation",
                        "Gradient Descent iteratively updates model parameters opposite to the gradient: theta_j := theta_j - alpha * (d/d theta_j) J(theta), where alpha is the learning rate.\n"
                        "- Batch Gradient Descent uses all m examples per step (smooth convergence, computationally heavy).\n"
                        "- Stochastic Gradient Descent (SGD) updates parameters per individual example (fast, noisy path).\n"
                        "- Mini-Batch Gradient Descent strikes an optimal balance using batches of 32 to 256 samples.\n\n"
                        "Analytical Solution: The Normal Equation computes theta = (X^T * X)^(-1) * X^T * y in O(p^3) time without iterative tuning."
                    ),
                    (
                        "Overfitting, Underfitting, and Regularization (L1 vs L2)",
                        "Overfitting occurs when a complex model fits noise in training data, exhibiting low training error but high test error (High Variance). Underfitting occurs when a model is too simple to capture trends (High Bias).\n\n"
                        "Regularization penalizes large parameter magnitudes to shrink variance:\n"
                        "- Ridge Regression (L2): Adds lambda * sum(theta_j^2) to cost function. Shrinks parameters smoothly toward zero.\n"
                        "- Lasso Regression (L1): Adds lambda * sum(|theta_j|) to cost function. Drives less informative coefficients to absolute zero, performing automatic feature selection."
                    ),
                ]
            },
            {
                "filename": "ML_Classification_Metrics.pdf",
                "title": "Machine Learning - Classification and Performance Evaluation",
                "pages": [
                    (
                        "Logistic Regression and Decision Boundaries",
                        "Logistic Regression predicts binary probabilities p in [0, 1] using the Sigmoid activation function: sigma(z) = 1 / (1 + exp(-z)), where z = theta^T * x.\n\n"
                        "Binary Cross-Entropy (Log-Loss): J(theta) = - (1/m) * sum(y_i * log(p_i) + (1 - y_i) * log(1 - p_i)). The decision boundary is the hyperplane theta^T * x = 0 separating predicted classes where probability equals 0.5."
                    ),
                    (
                        "Confusion Matrix, Precision, Recall, and F1-Score",
                        "Evaluation of classification models requires parsing the Confusion Matrix:\n"
                        "- True Positives (TP): Positive cases correctly predicted positive.\n"
                        "- False Positives (FP - Type I error): Negative cases incorrectly predicted positive.\n"
                        "- False Negatives (FN - Type II error): Positive cases incorrectly predicted negative.\n"
                        "- True Negatives (TN): Negative cases correctly predicted negative.\n\n"
                        "Metrics:\n"
                        "- Precision = TP / (TP + FP): Proportion of predicted positives that are actual positives.\n"
                        "- Recall (Sensitivity) = TP / (TP + FN): Proportion of actual positives captured by the model.\n"
                        "- F1-Score = 2 * (Precision * Recall) / (Precision + Recall): Harmonic mean balancing precision and recall."
                    ),
                    (
                        "ROC Curve, AUC, and Imbalanced Classification",
                        "The Receiver Operating Characteristic (ROC) curve plots True Positive Rate (Recall) against False Positive Rate (FPR = FP / (FP + TN)) across varying probability thresholds from 0 to 1.\n\n"
                        "Area Under the ROC Curve (AUC) measures the model's ability to rank positive instances higher than negative instances. An AUC of 0.5 represents random guessing, while 1.0 represents perfect discrimination. For heavily imbalanced datasets (e.g., fraud detection), Precision-Recall curves provide a much more informative metric than ROC-AUC."
                    ),
                ]
            },
            {
                "filename": "ML_Trees_Ensembles_Validation.pdf",
                "title": "Machine Learning - Decision Trees, Ensembles, and Validation",
                "pages": [
                    (
                        "Decision Trees and Impurity Metrics",
                        "Decision Trees perform recursive binary partitioning of the feature space. Split selection chooses the feature and threshold that maximizes Information Gain or minimizes node impurity.\n\n"
                        "Metrics:\n"
                        "- Entropy: H(S) = - sum(p_i * log2(p_i)). Information Gain = H(parent) - weighted_sum(H(children)).\n"
                        "- Gini Impurity: Gini = 1 - sum(p_i^2). Computationally faster as it avoids logarithmic calculations.\n"
                        "Unconstrained decision trees grow deep leaves and overfit training data, necessitating pre-pruning (max_depth, min_samples_split) or cost-complexity pruning."
                    ),
                    (
                        "Random Forests and Gradient Boosting Ensembles",
                        "Ensemble methods combine multiple base estimators to achieve superior predictive accuracy:\n"
                        "1. Bagging (Bootstrap Aggregation): Trains diverse models on random bootstrap subsets of data and averages predictions. Random Forests enhance Bagging by also subsampling features at each split, decorrelating individual trees and reducing variance.\n"
                        "2. Boosting: Trains models sequentially, where each new estimator corrects residual errors made by preceding estimators. Gradient Boosted Decision Trees (GBDT) fit trees to the negative gradient of the loss function."
                    ),
                    (
                        "Validation Protocols and Bias-Variance Decomposition",
                        "Expected Generalization Error decomposes into: Error = Bias^2 + Variance + IrreducibleNoise.\n\n"
                        "To estimate out-of-sample generalization reliably:\n"
                        "- K-Fold Cross Validation partitions training data into K equal folds, training on K-1 folds and validating on the held-out fold across K iterations.\n"
                        "- Stratified K-Fold ensures each fold preserves the original class label distribution, essential for imbalanced classification tasks."
                    ),
                ]
            },
        ],
        "mastery_seed": [
            {"concept": "Linear Regression", "topic": "Supervised Regression", "p_mastery": 0.91, "is_correct": True, "attempts": 7, "correct": 6},
            {"concept": "Classification Metrics", "topic": "Model Evaluation", "p_mastery": 0.66, "is_correct": True, "attempts": 5, "correct": 3},
            {"concept": "Bias-Variance Tradeoff", "topic": "Model Validation", "p_mastery": 0.36, "is_correct": False, "attempts": 6, "correct": 2, "gap_priority": 0.80, "status": "critical_gap", "action": "targeted_practice", "reason": "Struggling to diagnose high variance versus high bias from training curves."},
            {"concept": "Ensemble Methods (Boosting)", "topic": "Ensemble Learning", "p_mastery": 0.42, "is_correct": False, "attempts": 5, "correct": 2, "gap_priority": 0.75, "status": "needs_review", "action": "targeted_practice", "reason": "Unclear on sample weight re-distribution in AdaBoost."},
        ]
    }
]


def create_pdf(filepath: Path, pages: List[tuple]) -> None:
    """Creates a multi-page PDF document using PyMuPDF (fitz)."""
    doc = pymupdf.open()
    for title, content in pages:
        page = doc.new_page(width=595, height=842)  # A4 standard
        
        # Header banner
        page.draw_rect(pymupdf.Rect(40, 40, 555, 80), color=(0.12, 0.45, 0.95), fill=(0.93, 0.96, 1.0), width=1.5)
        page.insert_text(pymupdf.Point(55, 65), title, fontsize=14, fontname="helv", color=(0.08, 0.25, 0.65))

        # Main content body text
        rect = pymupdf.Rect(50, 100, 545, 780)
        page.insert_textbox(rect, content, fontsize=10.5, fontname="helv", color=(0.15, 0.15, 0.15), lineheight=1.4)
    
    doc.save(str(filepath))
    doc.close()


async def check_health():
    """Phase 0 Diagnostic health check."""
    print("\n--- PHASE 0: Health Check ---")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. FastAPI Direct
        try:
            r = await client.get(f"{FASTAPI_URL}/api/v1/health")
            print(f"[FastAPI Direct :8000] Status: {r.status_code}")
            if r.status_code == 200:
                h = r.json()
                print(f"  Backend: {h.get('backend')}, Database: {h.get('database', {}).get('status')}, Vector: {h.get('vector', {}).get('capability')}")
            else:
                print(f"  Warning: FastAPI health returned HTTP {r.status_code}")
        except Exception as e:
            print(f"  Error connecting to FastAPI at {FASTAPI_URL}: {e}")
            raise SystemExit("FastAPI backend must be running on port 8000 before seeding.")

        # 2. Next.js Proxy
        try:
            r = await client.get(f"{PROXY_URL}/api/v1/health")
            print(f"[Next.js Proxy :3000] Status: {r.status_code}")
        except Exception as e:
            print(f"  Note: Next.js proxy on :3000 is not reachable ({e}). Proceeding directly via FastAPI backend.")


async def resolve_or_create_workspace(client: httpx.AsyncClient, subject: Dict[str, Any]) -> str:
    """Rule 3 Exact Name Lookup."""
    name = subject["name"]
    res = await client.get(f"{FASTAPI_URL}/api/v1/workspaces", params={"name": name})
    if res.status_code != 200:
        raise RuntimeError(f"Failed to query workspaces: HTTP {res.status_code} - {res.text}")

    data = res.json()
    matches = [w for w in data.get("workspaces", []) if w["name"] == name]

    if len(matches) == 1:
        ws_id = matches[0]["id"]
        print(f"  Found existing workspace: '{name}' -> Database ID: {ws_id}")
        return ws_id
    elif len(matches) == 0:
        print(f"  Creating workspace: '{name}'...")
        payload = {
            "name": name,
            "description": subject["description"],
            "goal": subject["goal"],
            "level": subject["level"],
            "target_date": "2026-12-31",
            "daily_target_minutes": 45,
            "icon_name": subject["icon_name"],
        }
        create_res = await client.post(f"{FASTAPI_URL}/api/v1/workspaces", json=payload)
        if create_res.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create workspace '{name}': {create_res.status_code} - {create_res.text}")
        ws_id = create_res.json()["id"]
        print(f"  Created workspace: '{name}' -> Database ID: {ws_id}")
        return ws_id
    else:
        raise RuntimeError(f"Conflict: Found {len(matches)} workspaces matching exact name '{name}'. Aborting per Rule 3.")


async def upload_documents(client: httpx.AsyncClient, workspace_id: str, subject: Dict[str, Any], temp_dir: Path):
    """Generates and uploads demonstration PDFs idempotently."""
    # Check existing docs in workspace
    r = await client.get(f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/documents")
    existing_filenames = set()
    if r.status_code == 200:
        docs = r.json().get("documents", [])
        existing_filenames = {d["filename"] for d in docs}

    for doc_info in subject["docs"]:
        fn = doc_info["filename"]
        if fn in existing_filenames:
            print(f"    Document '{fn}' already indexed. Skipping upload.")
            continue

        pdf_path = temp_dir / fn
        create_pdf(pdf_path, doc_info["pages"])
        print(f"    Generated PDF: {fn} ({pdf_path.stat().st_size} bytes)")

        with open(pdf_path, "rb") as f:
            files = {"file": (fn, f, "application/pdf")}
            data = {"title": doc_info["title"]}
            up_res = await client.post(
                f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/documents",
                files=files,
                data=data,
            )
            if up_res.status_code in (200, 201):
                doc_id = up_res.json().get("id")
                chunks_count = up_res.json().get("chunks_count", 0)
                print(f"    Uploaded '{fn}' -> Doc ID: {doc_id}, Chunks: {chunks_count}")
            else:
                print(f"    Error uploading '{fn}': HTTP {up_res.status_code} - {up_res.text}")


async def seed_mastery_and_gaps(client: httpx.AsyncClient, workspace_id: str, subject: Dict[str, Any]):
    """Seeds BKT concept mastery, knowledge gaps, and triggers topic mastery calculations via FastAPI API."""
    res = await client.post(
        f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/mastery/seed",
        json={
            "user_ids": DEMO_USERS,
            "concepts": subject["mastery_seed"],
        },
    )
    if res.status_code == 200:
        print(f"    Seeded {res.json().get('seeded_concepts')} concepts into FastAPI for '{subject['name']}'")
    else:
        print(f"    Warning seeding mastery: HTTP {res.status_code} - {res.text}")


async def seed_secondary_features(client: httpx.AsyncClient, workspace_id: str, subject: Dict[str, Any]):
    """Generates flashcards, study plans, and seed activities."""
    # 1. Generate flashcards
    fc_res = await client.post(f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/flashcards/generate")
    if fc_res.status_code in (200, 201):
        total_fc = fc_res.json().get("total_count", 0)
        print(f"    Generated {total_fc} flashcards for '{subject['name']}'")

    # 2. Generate study plan
    sp_res = await client.post(f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/study-plan/generate")
    if sp_res.status_code in (200, 201):
        tasks = len(sp_res.json().get("tasks", []))
        print(f"    Generated adaptive study plan with {tasks} tasks for '{subject['name']}'")

    # 3. Seed initial activity events
    events = [
        ("Diagnostic Assessment Completed", f"Initial diagnostic baseline established for {subject['name']}.", "quiz_completed"),
        ("Learning Documents Indexed", f"3 demonstration resources parsed and vector-indexed.", "source_added"),
        ("Adaptive Study Plan Active", f"Targeted review schedule aligned with identified knowledge gaps.", "roadmap_adapted"),
    ]
    for title, desc, event_type in events:
        await client.post(
            f"{FASTAPI_URL}/api/v1/workspaces/{workspace_id}/activity",
            json={
                "event_type": event_type,
                "title": title,
                "description": desc,
            },
        )


async def main():
    print("====================================================")
    print("      LumoraAI Presentation Demo Seeding Tool       ")
    print("====================================================")

    # 1. Health check
    await check_health()

    temp_docs_dir = PROJECT_ROOT / "temp_demo_docs"
    temp_docs_dir.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n--- Seeding 4 Presentation Workspaces ---")
        for subject in SUBJECTS_CONFIG:
            name = subject["name"]
            print(f"\nProcessing Workspace: '{name}'...")
            
            # Rule 3 Workspace Resolution
            ws_id = await resolve_or_create_workspace(client, subject)

            # Upload 3 PDFs
            await upload_documents(client, ws_id, subject, temp_docs_dir)

            # Seed BKT & Topic Mastery
            print("    Seeding BKT mastery & knowledge gaps...")
            await seed_mastery_and_gaps(client, ws_id, subject)

            # Secondary features (Flashcards, Study Plan, Activity)
            print("    Seeding flashcards, study plan, and activity...")
            await seed_secondary_features(client, ws_id, subject)

    print("\n====================================================")
    print("   Seeding Completed Successfully! Demo is Ready.    ")
    print("====================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
