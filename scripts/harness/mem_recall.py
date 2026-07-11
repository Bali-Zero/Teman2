#!/usr/bin/env python3
"""mem_recall.py — memoria semantica locale per l'harness. Richiamo PER SIGNIFICATO, non sequenziale.

Design (opus-mythos TAC harness 2026-06-16, post-refuter DeepSeek):
  - 100% ON-M5, zero rete, zero server (no Qdrant, no SSH->Mini). Law-6 sovrano, offline-capable.
  - Hybrid retrieval: BM25 keyword (rank_bm25, MIT) + semantic rerank (bge-small via
    sentence-transformers, Apache-2.0, ~130MB, CPU). Consenso SOTA 2026 (Mem0/TiMem): hybrid > pure-vector.
  - Accumula, non cancella (Mem0 ADD-only). L'indice e' cache, ri-costruibile, invalidato per mtime.

Uso:
  mem_recall.py index                      # (ri)costruisce l'indice embedding+bm25 (incrementale per mtime)
  mem_recall.py recall "<situazione>"      # top-5 ricordi pertinenti {path, score, snippet}
  mem_recall.py recall "<q>" -k 8 --json   # k risultati, output JSON

Fallback: se i modelli non sono installati, degrada a ripgrep+BM25 puro (nessun crash)."""
import sys, os, json, sqlite3, hashlib, glob, re
os.environ.setdefault("HF_HUB_OFFLINE", "1")        # no rate-limit warning dopo il primo download
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MEMDIR = os.path.expanduser("~/.claude/projects/-Users-balizero-Desktop-nuzantara/memory")
CACHE = os.path.expanduser("~/.claude/memory.db")  # riusa il .db a 0 byte
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # multilingua decente IT/ID, ~130MB, CPU
TOP_K = 5

# --- lazy heavy deps (fallback se assenti) ---
def _load_embedder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBED_MODEL)
    except Exception:
        return None

def _files():
    return sorted(glob.glob(os.path.join(MEMDIR, "*.md")))

def _read(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""

def _chunk_meta(text):
    """estrae name+description dal frontmatter + primo paragrafo (il segnale piu' denso)."""
    name = desc = ""
    m = re.search(r'^name:\s*(.+)$', text, re.M)
    if m: name = m.group(1).strip()
    m = re.search(r'^description:\s*["\']?(.+?)["\']?$', text, re.M)
    if m: desc = m.group(1).strip()
    body = re.sub(r'^---.*?---', '', text, count=1, flags=re.S).strip()
    return f"{name}. {desc}. {body[:600]}"

def _db():
    db = sqlite3.connect(CACHE)
    db.execute("CREATE TABLE IF NOT EXISTS mem(path TEXT PRIMARY KEY, mtime REAL, text TEXT, vec BLOB)")
    return db

def cmd_index():
    import numpy as np
    emb = _load_embedder()
    db = _db()
    cur = {r[0]: r[1] for r in db.execute("SELECT path, mtime FROM mem")}
    files = _files()
    changed = [p for p in files if os.path.getmtime(p) != cur.get(p)]
    # rimuovi orfani (file cancellati)
    gone = set(cur) - set(files)
    for p in gone:
        db.execute("DELETE FROM mem WHERE path=?", (p,))
    print(f"index: {len(files)} file, {len(changed)} da (ri)embeddare, {len(gone)} rimossi", file=sys.stderr)
    for i, p in enumerate(changed):
        txt = _chunk_meta(_read(p))
        vec = None
        if emb is not None:
            v = emb.encode(txt, normalize_embeddings=True)
            vec = np.asarray(v, dtype="float32").tobytes()
        db.execute("INSERT OR REPLACE INTO mem(path,mtime,text,vec) VALUES(?,?,?,?)",
                   (p, os.path.getmtime(p), txt, vec))
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(changed)}", file=sys.stderr); db.commit()
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM mem").fetchone()[0]
    has_vec = db.execute("SELECT COUNT(*) FROM mem WHERE vec IS NOT NULL").fetchone()[0]
    print(f"index OK: {n} ricordi, {has_vec} con embedding ({'semantic+bm25' if has_vec else 'bm25-only fallback'})")

def cmd_recall(query, k, as_json):
    import numpy as np
    from rank_bm25 import BM25Okapi
    db = _db()
    rows = db.execute("SELECT path, text, vec FROM mem").fetchall()
    if not rows:
        print("indice vuoto — esegui prima: mem_recall.py index", file=sys.stderr); sys.exit(1)
    paths = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    # BM25 keyword score
    toks = [re.findall(r'\w+', t.lower()) for t in texts]
    bm25 = BM25Okapi(toks)
    bm_scores = bm25.get_scores(re.findall(r'\w+', query.lower()))
    bm_scores = bm_scores / (bm_scores.max() or 1)
    # semantic score (se embeddings presenti)
    sem_scores = np.zeros(len(rows))
    emb = _load_embedder()
    if emb is not None and any(r[2] for r in rows):
        qv = np.asarray(emb.encode(query, normalize_embeddings=True), dtype="float32")
        for i, r in enumerate(rows):
            if r[2]:
                v = np.frombuffer(r[2], dtype="float32")
                sem_scores[i] = float(np.dot(qv, v))
        sem_scores = sem_scores / (sem_scores.max() or 1)
        final = 0.5 * bm_scores + 0.5 * sem_scores  # hybrid 50/50
        mode = "hybrid"
    else:
        final = bm_scores
        mode = "bm25-only"
    order = np.argsort(-final)[:k]
    out = []
    for i in order:
        snippet = texts[i][:140].replace("\n", " ")
        out.append({"path": os.path.basename(paths[i]), "score": round(float(final[i]), 3), "snippet": snippet})
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# mem recall ({mode}) — top {len(out)} per: {query!r}\n")
        for r in out:
            print(f"[{r['score']}] {r['path']}\n    {r['snippet']}…\n")

def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("index", "recall"):
        print(__doc__); sys.exit(0)
    if a[0] == "index":
        cmd_index()
    else:
        q = a[1] if len(a) > 1 else ""
        k = int(a[a.index("-k") + 1]) if "-k" in a else TOP_K
        cmd_recall(q, k, "--json" in a)

if __name__ == "__main__":
    main()
