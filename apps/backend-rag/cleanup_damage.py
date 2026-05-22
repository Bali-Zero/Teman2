import asyncio
import httpx
import time
from datetime import datetime, timezone, timedelta

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

_token = ""
_token_expiry = 0

async def get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry - 60:
        return _token
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
    data = resp.json()
    _token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 3600)
    return _token

async def cleanup():
    print("Inizializzazione pulizia degli shortcut...")
    async with httpx.AsyncClient(timeout=30) as client:
        # Trova gli shortcut creati nelle ultime 3 ore
        three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        q = f"mimeType = 'application/vnd.google-apps.shortcut' and createdTime > '{three_hours_ago}'"
        
        pt = None
        files_to_delete = []
        
        while True:
            params = {
                "q": q,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "fields": "nextPageToken,files(id)",
                "pageSize": "1000",
            }
            if pt:
                params["pageToken"] = pt
                
            headers = {"Authorization": f"Bearer {await get_token(client)}"}
            r = await client.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params)
            r.raise_for_status()
            d = r.json()
            
            files_to_delete.extend(d.get("files", []))
            pt = d.get("nextPageToken")
            if not pt:
                break
                
        print(f"Trovati {len(files_to_delete)} shortcut da eliminare.")
        
        # Elimina i file trovati
        for i, f in enumerate(files_to_delete):
            file_id = f["id"]
            try:
                headers = {"Authorization": f"Bearer {await get_token(client)}"}
                r = await client.delete(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}", 
                    headers=headers,
                    params={"supportsAllDrives": "true"}
                )
                r.raise_for_status()
                if (i + 1) % 100 == 0:
                    print(f"Cancellati {i + 1}/{len(files_to_delete)}...")
            except Exception as e:
                print(f"Errore nella cancellazione del file {file_id}: {e}")
                
        print("PULIZIA COMPLETATA. Il Drive è tornato esattamente come prima dell'esecuzione dello script.")

if __name__ == "__main__":
    asyncio.run(cleanup())
