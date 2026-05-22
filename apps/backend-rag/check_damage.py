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

async def check():
    async with httpx.AsyncClient(timeout=30) as client:
        # We want to find all shortcuts created in the last 2 hours.
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        
        q = f"mimeType = 'application/vnd.google-apps.shortcut' and createdTime > '{two_hours_ago}'"
        
        pt = None
        count = 0
        parents = set()
        
        print(f"Searching Drive for shortcuts created after {two_hours_ago}...")
        
        while True:
            params = {
                "q": q,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "fields": "nextPageToken,files(id,name,parents)",
                "pageSize": "1000",
            }
            if pt:
                params["pageToken"] = pt
                
            headers = {"Authorization": f"Bearer {await get_token(client)}"}
            r = await client.get("https://www.googleapis.com/drive/v3/files", headers=headers, params=params)
            r.raise_for_status()
            d = r.json()
            
            files = d.get("files", [])
            count += len(files)
            
            for f in files:
                p = f.get("parents", [])
                if p:
                    parents.add(p[0])
            
            pt = d.get("nextPageToken")
            if not pt:
                break
                
        print(f"\n--- DAMAGE REPORT ---")
        print(f"Total shortcuts created in the last 2 hours: {count}")
        print(f"Number of distinct destination folders affected: {len(parents)}")
        
        # Let's get the names of the affected folders
        if parents:
            print("\nFetching names of affected folders (first 20)...")
            affected_names = []
            for i, p_id in enumerate(list(parents)[:20]):
                try:
                    headers = {"Authorization": f"Bearer {await get_token(client)}"}
                    r = await client.get(f"https://www.googleapis.com/drive/v3/files/{p_id}?fields=name", headers=headers)
                    affected_names.append(f"{r.json().get('name', 'Unknown')} (ID: {p_id})")
                except:
                    pass
            for name in affected_names:
                print(f"  - {name}")

asyncio.run(check())
