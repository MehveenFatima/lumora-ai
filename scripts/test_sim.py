import numpy as np, hashlib

STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'about', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'from', 'up', 'down', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'can',
    'could', 'should', 'would', 'may', 'might', 'must', 'shall', 'what', 'how',
    'why', 'when', 'where', 'who', 'which', 'tell', 'give', 'me', 'you',
    'this', 'that', 'these', 'those', 'it', 'its', 'we', 'they', 'them', 'their', 'of', 'as'
}

def stem(w):
    w = w.lower().strip(".,?!-;:()[]\"'")
    for suffix in ["tion", "tions", "ing", "ings", "ed", "es", "s"]:
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[:-len(suffix)]
    return w

def generate_embedding(text: str, dim: int = 768):
    vec = np.zeros(dim, dtype=np.float32)
    raw_words = text.lower().replace('.', ' ').replace(',', ' ').replace('?', ' ').replace('-', ' ').split()
    words = [stem(w) for w in raw_words if len(w) > 2 and w not in STOP_WORDS]
    if not words:
        words = raw_words
    for idx, w in enumerate(words):
        h1 = int.from_bytes(hashlib.md5(w.encode('utf-8')).digest()[:4], 'big') % dim
        h2 = int.from_bytes(hashlib.sha256(w.encode('utf-8')).digest()[:4], 'big') % dim
        vec[h1] += 2.0
        vec[h2] += 1.0
        if len(w) >= 3:
            h_pref = int.from_bytes(hashlib.md5(w[:4].encode('utf-8')).digest()[:4], 'big') % dim
            vec[h_pref] += 1.5

    norm = np.linalg.norm(vec)
    if norm == 0:
        return [0.0] * dim
    return (vec / norm).tolist()

doc1 = 'In directed cycle detection, a back-edge points to an ancestor currently on the recursion stack.'
q1 = 'How do we detect cycles in directed graphs with back edges?'
unrelated = 'Quantum computing utilizes qubits to achieve superposition and entanglement'

v_doc1 = np.array(generate_embedding(doc1))
v_q1 = np.array(generate_embedding(q1))
v_un = np.array(generate_embedding(unrelated))

print('Tutor test related:', np.dot(v_doc1, v_q1))
print('Tutor test unrelated:', np.dot(v_un, v_q1))
