import os
import re
import glob
import zipfile
import requests
import logging
import uuid


# --- ENV LOADER ---
def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        print(f"📄 Loading secrets from {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    if not os.environ.get(key):
                        os.environ[key] = value


# --- CONFIGURATION ---
load_env_file()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "legal_unified"
VECTOR_SIZE = 1536
SOURCE_DIR = "nuzantara_laws"
ZIP_FILE = "nuzantara_laws.zip"
GDRIVE_ID = "1Lx4y9TQ45uBUyvNzeHiHinxo_k_WOMmm"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- REGEX PATTERNS ---
NOISE_PATTERNS = [
    re.compile(r"^Halaman\s+\d+\s+dari\s+\d+", re.IGNORECASE | re.MULTILINE),
    re.compile(
        r"^Salinan sesuai dengan aslinya.*?(?=\n)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    re.compile(r"^PRESIDEN REPUBLIK INDONESIA\s*\n", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*-\s*\d+\s*-\s*$", re.MULTILINE),
    re.compile(r"\n{3,}", re.MULTILINE),
    re.compile(r"^\s*\d+\s*$", re.MULTILINE),
]
LEGAL_TYPE_PATTERN = re.compile(
    r"(UNDANG-UNDANG|PERATURAN PEMERINTAH|KEPUTUSAN PRESIDEN|PERATURAN MENTERI|QANUN|PERATURAN DAERAH|PERATURAN KEPALA)",
    re.IGNORECASE,
)
LEGAL_TYPE_ABBREV = {
    "UNDANG-UNDANG": "UU",
    "PERATURAN PEMERINTAH": "PP",
    "KEPUTUSAN PRESIDEN": "Keppres",
    "PERATURAN MENTERI": "Permen",
    "QANUN": "Qanun",
    "PERATURAN DAERAH": "Perda",
    "PERATURAN KEPALA": "Perkep",
}
NUMBER_PATTERN = re.compile(r"NOMOR\s+(\d+[A-Z]?)(?:[/-]\d+)?", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"TAHUN\s+(\d{4})", re.IGNORECASE)
TOPIC_PATTERN = re.compile(
    r"TENTANG\s+(.+?)(?=DENGAN RAHMAT|Menimbang|Mengingat|$)", re.IGNORECASE | re.DOTALL
)
PASAL_PATTERN = re.compile(
    r"^Pasal\s+(\d+[A-Z]?)\s*(.+?)(?=^Pasal\s+\d+|^BAB\s+|^Penjelasan|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
BAB_PATTERN = re.compile(
    r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s+(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE
)
AYAT_PATTERN = re.compile(
    r"(?:^|\n)\s*\((\d+)\)\s*(.+?)(?=(?:^|\n)\s*\(\d+\)|$)", re.MULTILINE | re.DOTALL
)


# --- CLASSES ---
class LegalCleaner:
    def clean(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text
        for pattern in NOISE_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\n\s+\n", "\n\n", cleaned)
        cleaned = re.sub(
            r"Pasal\s+(\d+[A-Z]?)", r"Pasal \1", cleaned, flags=re.IGNORECASE
        )
        return cleaned.strip()


class LegalMetadataExtractor:
    def extract(self, text: str) -> dict:
        meta = {
            "type": "UNKNOWN",
            "number": "UNKNOWN",
            "year": "UNKNOWN",
            "topic": "UNKNOWN",
        }
        type_match = LEGAL_TYPE_PATTERN.search(text)
        if type_match:
            doc_type = type_match.group(1).upper()
            meta["type"] = doc_type
            meta["type_abbrev"] = LEGAL_TYPE_ABBREV.get(doc_type, doc_type)
        num_match = NUMBER_PATTERN.search(text)
        if num_match:
            meta["number"] = num_match.group(1)
        year_match = YEAR_PATTERN.search(text)
        if year_match:
            meta["year"] = year_match.group(1)
        topic_match = TOPIC_PATTERN.search(text)
        if topic_match:
            meta["topic"] = re.sub(r"\s+", " ", topic_match.group(1).strip())[:200]
        return meta


class LegalStructureParser:
    def parse(self, text: str) -> dict:
        structure = {"batang_tubuh": []}
        bab_matches = list(BAB_PATTERN.finditer(text))
        for i, match in enumerate(bab_matches):
            bab_num = match.group(1)
            bab_title = match.group(2).strip()
            start = match.end()
            end = bab_matches[i + 1].start() if i + 1 < len(bab_matches) else len(text)
            pasal_list = []
            pasal_matches = list(PASAL_PATTERN.finditer(text[start:end]))
            for p_match in pasal_matches:
                pasal_list.append({"number": p_match.group(1)})
            structure["batang_tubuh"].append(
                {"number": bab_num, "title": bab_title, "pasal": pasal_list}
            )
        return structure


class LegalChunker:
    def __init__(self):
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, chunk_overlap=200
        )

    def chunk(self, text: str, metadata: dict, structure: dict) -> list:
        chunks = []
        pasal_matches = list(PASAL_PATTERN.finditer(text))
        if not pasal_matches:
            raw_chunks = self.fallback_splitter.split_text(text)
            context = self._build_context(metadata)
            for rc in raw_chunks:
                chunks.append(self._create_chunk(rc, context, metadata))
            return chunks
        for match in pasal_matches:
            pasal_num = match.group(1)
            pasal_text = match.group(2).strip()
            bab_context = self._find_bab_for_pasal(structure, pasal_num)
            if len(pasal_text) > 3000:
                ayat_matches = list(AYAT_PATTERN.finditer(pasal_text))
                if ayat_matches:
                    for am in ayat_matches:
                        ayat_num = am.group(1)
                        ayat_text = am.group(2).strip()
                        context = self._build_context(
                            metadata, bab_context, f"Pasal {pasal_num}"
                        )
                        chunks.append(
                            self._create_chunk(
                                f"Ayat ({ayat_num})\n{ayat_text}",
                                context,
                                metadata,
                                pasal_num,
                            )
                        )
                    continue
            context = self._build_context(metadata, bab_context, f"Pasal {pasal_num}")
            chunks.append(self._create_chunk(pasal_text, context, metadata, pasal_num))
        return chunks

    def _build_context(self, meta, bab=None, pasal=None):
        parts = [
            meta.get("type_abbrev", "UNK"),
            f"NO {meta.get('number', '?')}",
            f"TAHUN {meta.get('year', '?')}",
            f"TENTANG {meta.get('topic', 'UNK')}",
        ]
        if bab:
            parts.append(bab)
        if pasal:
            parts.append(pasal)
        return f"[CONTEXT: {' - '.join(parts)}]"

    def _create_chunk(self, content, context, meta, pasal_num=None):
        chunk_text = f"{context}\n\n{content}"
        c = {"text": chunk_text, "has_context": True}
        c.update(meta)
        if pasal_num:
            c["pasal_number"] = pasal_num
        return c

    def _find_bab_for_pasal(self, structure, pasal_num):
        for bab in structure.get("batang_tubuh", []):
            for p in bab.get("pasal", []):
                if p.get("number") == pasal_num:
                    return f"BAB {bab.get('number')} - {bab.get('title', '')}"
        return None


# --- API HELPERS (PURE REQUESTS) ---
def qdrant_request(method, endpoint, data=None):
    url = f"{QDRANT_URL}/{endpoint}"
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
    # Use verify=False to bypass SSL issues
    response = requests.request(
        method, url, headers=headers, json=data, verify=False, timeout=60
    )
    if response.status_code not in [200, 201]:
        raise Exception(f"Qdrant Error {response.status_code}: {response.text}")
    return response.json()


def robust_embed(texts, api_key):
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    clean_texts = [t.replace("\n", " ") for t in texts]
    data = {"input": clean_texts, "model": "text-embedding-3-small"}
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code != 200:
        raise Exception(f"OpenAI API Error {response.status_code}: {response.text}")
    return [d["embedding"] for d in response.json()["data"]]


def main():
    print("🦖 THE LAW EATER (PURE REQUESTS EDITION)")

    # 1. Credentials Check
    if not QDRANT_URL or not QDRANT_API_KEY or not OPENAI_API_KEY:
        print("❌ Missing credentials! Please ensure .env file is correct.")
        return

    # 2. Download Data
    if not os.path.exists(ZIP_FILE):
        print("📥 Downloading data...")
        try:
            import gdown

            gdown.download(id=GDRIVE_ID, output=ZIP_FILE, quiet=False)
        except ImportError:
            print(
                "❌ 'gdown' not installed. Please run 'pip install gdown' and try again."
            )
            return

    if not os.path.exists(SOURCE_DIR):
        print("📦 Unzipping...")
        with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:
            zip_ref.extractall(SOURCE_DIR)

    # 3. Setup Qdrant (REST API)
    print(f"🔌 Connecting to Qdrant at {QDRANT_URL}...")
    try:
        # Check if collection exists
        try:
            qdrant_request("GET", f"collections/{COLLECTION_NAME}")
            print(f"   ⚠️ Deleting existing collection '{COLLECTION_NAME}'...")
            qdrant_request("DELETE", f"collections/{COLLECTION_NAME}")
        except Exception:
            pass  # Collection probably doesn't exist

        print(f"   ✨ Creating collection '{COLLECTION_NAME}'...")
        qdrant_request(
            "PUT",
            f"collections/{COLLECTION_NAME}",
            {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}},
        )
        print("   ✅ Collection ready!")
    except Exception as e:
        print(f"❌ Failed to setup Qdrant: {e}")
        return

    # 4. Process
    cleaner = LegalCleaner()
    extractor = LegalMetadataExtractor()
    parser = LegalStructureParser()
    chunker = LegalChunker()

    from langchain_community.document_loaders import PyPDFLoader

    pdf_files = glob.glob(f"{SOURCE_DIR}/**/*.pdf", recursive=True)
    print(f"📚 Found {len(pdf_files)} PDFs. Starting ingestion...")

    for i, pdf_file in enumerate(pdf_files):
        try:
            print(
                f"[{i + 1}/{len(pdf_files)}] Processing {os.path.basename(pdf_file)}..."
            )

            # Check Header
            with open(pdf_file, "rb") as f:
                if f.read(4) != b"%PDF":
                    print("   ⚠️ Invalid PDF header. Skipping.")
                    continue

            loader = PyPDFLoader(pdf_file)
            pages = loader.load()
            raw_text = "\n".join([p.page_content for p in pages])

            if len(raw_text) < 100:
                print("   ⚠️ Text too short. Skipping.")
                continue

            cleaned_text = cleaner.clean(raw_text)
            meta = extractor.extract(cleaned_text)
            if meta["type"] == "UNKNOWN":
                meta["topic"] = os.path.basename(pdf_file)
            structure = parser.parse(cleaned_text)
            chunks = chunker.chunk(cleaned_text, meta, structure)

            if chunks:
                texts = [c["text"] for c in chunks]
                vectors = []
                # Mini-batch embedding
                batch_size = 10
                for k in range(0, len(texts), batch_size):
                    batch = texts[k : k + batch_size]
                    vectors.extend(robust_embed(batch, OPENAI_API_KEY))

                points = []
                for j, chunk in enumerate(chunks):
                    # Generate a deterministic UUID based on metadata and chunk index
                    seed_str = f"{meta.get('type_abbrev')}-{meta.get('number')}-{meta.get('year')}_chunk_{j}_{chunk['text'][:20]}"
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed_str))

                    points.append(
                        {"id": point_id, "vector": vectors[j], "payload": chunk}
                    )

                # Upload via REST API
                qdrant_request(
                    "PUT",
                    f"collections/{COLLECTION_NAME}/points?wait=true",
                    {"points": points},
                )
                print(f"   ✅ Uploaded {len(points)} chunks.")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("🎉 Ingestion Complete!")


if __name__ == "__main__":
    main()
