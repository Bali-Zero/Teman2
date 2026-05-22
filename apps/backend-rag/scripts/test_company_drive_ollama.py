import asyncio
import io
import json
import logging
import subprocess

import httpx
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

# Configurazione Drive
OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

# L'ID della cartella "Company_CRM" di un'azienda reale.
# Esempio: PT Predmet Development Bali
TEST_COMPANY_FOLDER_ID = "1TCJz0gE4YglNHYYHhlooQVd-V9120vPe"

async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

async def list_files_in_folder(client: httpx.AsyncClient, token: str, folder_id: str) -> list[dict]:
    r = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name,mimeType)",
            "pageSize": "10",
        },
    )
    r.raise_for_status()
    return r.json().get("files", [])

async def list_subfolders(client: httpx.AsyncClient, token: str, folder_id: str) -> dict[str, str]:
    r = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name)",
            "pageSize": "100",
        },
    )
    r.raise_for_status()
    return {f["name"]: f["id"] for f in r.json().get("files", [])}

async def classify_with_ollama(text: str) -> str:
    prompt = f"""Sei un classificatore automatico di documenti legali indonesiani.
Regole:
1. Devi rispondere SOLO con il nome esatto della cartella tra queste: '00_AKTA', '01_NIB', '02_NPWP', '03_Profile_Perseroan', o '99_Misc'.
2. Non aggiungere nient'altro.

Testo del documento:
{text[:2000]}

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

async def process_company_folder():
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await get_token(client)
        
        logger.info("Scansionando sottocartelle della compagnia...")
        subfolders = await list_subfolders(client, token, TEST_COMPANY_FOLDER_ID)
        
        # Troviamo la cartella 99_Misc o elaboriamo la radice se non c'è
        misc_id = subfolders.get("99_Misc")
        if not misc_id:
            logger.info("Nessuna cartella 99_Misc trovata. Analizzo la radice della compagnia...")
            files_to_check = await list_files_in_folder(client, token, TEST_COMPANY_FOLDER_ID)
        else:
            logger.info("Analizzando i file sparsi in 99_Misc...")
            files_to_check = await list_files_in_folder(client, token, misc_id)

        if not files_to_check:
            logger.info("Nessun file sparso trovato per il test.")
            return

        for f in files_to_check:
            filename = f['name']
            logger.info(f"Trovato file: {filename}")
            
            # Filtro rapido (Heuristic Router)
            lower_name = filename.lower()
            if "npwp" in lower_name:
                logger.info(f" -> [HEURISTIC] Smistato in: 02_NPWP")
                continue
            if "nib" in lower_name:
                logger.info(f" -> [HEURISTIC] Smistato in: 01_NIB")
                continue
            if "akta" in lower_name:
                logger.info(f" -> [HEURISTIC] Smistato in: 00_AKTA")
                continue
                
            # Se è PDF e non è ovvio, estraiamo il testo e mandiamo a Ollama
            if f['mimeType'] == 'application/pdf':
                logger.info(f" -> Nome ambiguo. Scarico il PDF per leggerlo...")
                resp = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{f['id']}?alt=media",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    try:
                        reader = PdfReader(io.BytesIO(resp.content))
                        text = ""
                        for page in reader.pages[:2]: # Prime 2 pagine
                            text += page.extract_text() + "\n"
                        
                        logger.info(f" -> Testo estratto ({len(text)} chars). Chiedo a Ollama su Mini...")
                        category = await classify_with_ollama(text)
                        logger.info(f" -> [OLLAMA AI] File classificato come: {category}")
                    except Exception as e:
                        logger.error(f" -> Errore parsing PDF: {e}")
                else:
                    logger.error(f" -> Errore download PDF: {resp.status_code}")
            else:
                logger.info(" -> Formato non supportato per AI, lo metto in 99_Misc")

if __name__ == "__main__":
    asyncio.run(process_company_folder())
