import urllib.request
import fitz
import os

os.makedirs('backend/data/seed_pdfs', exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

targets = {
    'xv6': ('https://pdos.csail.mit.edu/6.1810/2025/xv6/book-riscv-rev5.pdf', 'backend/data/seed_pdfs/xv6_book_riscv.pdf'),
    'cmu_db': ('https://15445.courses.cs.cmu.edu/spring2025/notes/01-relationalmodel.pdf', 'backend/data/seed_pdfs/cmu_15445_relational_model.pdf'),
    'cs229': ('https://cs229.stanford.edu/notes2020spring/cs229-notes1.pdf', 'backend/data/seed_pdfs/cs229_lecture1.pdf'),
    'rfc9293': ('https://www.rfc-editor.org/rfc/rfc9293.pdf', 'backend/data/seed_pdfs/rfc9293_tcp.pdf'),
}

for k, (url, dest) in targets.items():
    print(f'Downloading {k} from {url}...')
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
        with open(dest, 'wb') as f:
            f.write(data)
        doc = fitz.open(dest)
        print(f'  -> Saved {dest}: {len(data)/1024:.1f} KB, pages={len(doc)}, is_pdf={data[:4] == b"%PDF"}')
    except Exception as e:
        print(f'  -> FAILED {k}: {e}')
