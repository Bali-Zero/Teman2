import asyncio
import json
import logging
import subprocess

from pypdf import PdfReader

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

async def classify_with_ollama(text: str) -> str:
    prompt = f"""Sei un classificatore automatico di documenti legali indonesiani.
Regole:
1. Devi rispondere SOLO con il nome esatto della cartella tra queste: '00_AKTA', '01_NIB', '02_NPWP', '03_Profile_Perseroan', o '99_Misc'.
2. Non aggiungere nient'altro.

Testo del documento:
{text[:2500]}

Rispondi con il nome della cartella:"""

    payload = json.dumps({"model": "qwen2.5:7b", "prompt": prompt, "stream": False})
    cmd = [
        "ssh", "mini",
        "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
        "-d", f"'{payload}'"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get("response", "99_Misc").strip()
    return "99_Misc"

async def process_local_pdf():
    pdf_path = "/Users/nuzantara/Desktop/nuzantara/.gemini/tmp/company_pdfs/1755.pdf"
    logger.info(f"Leggo il file PDF locale REALE: {pdf_path}")

    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages[:2]: # Prime 2 pagine
            text += page.extract_text() + "\n"

        logger.info(f" -> Testo estratto ({len(text)} chars). Chiedo a Ollama su Mini...")
        category = await classify_with_ollama(text)
        logger.info(f" -> [OLLAMA AI] File classificato come: {category}")
    except Exception as e:
        logger.error(f" -> Errore parsing PDF: {e}")

if __name__ == "__main__":
    asyncio.run(process_local_pdf())
