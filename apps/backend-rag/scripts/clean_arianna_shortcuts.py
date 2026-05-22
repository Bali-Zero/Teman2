import asyncio
import time

import httpx

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
    _token_expiry = time.time() + data["expires_in"]
    return _token

ARIANNA_DRIVE_ID = "1b323yfGvo0wpPCwiOb1JeMpkLcgiHrRB"

async def list_files(client, folder_id):
    token = await get_token(client)
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "nextPageToken, files(id, name, mimeType)",
        "pageSize": 1000,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true"
    }
    headers = {"Authorization": f"Bearer {token}"}
    files = []
    while True:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            print("Error listing files:", resp.text)
            break
        data = resp.json()
        files.extend(data.get("files", []))
        if "nextPageToken" in data:
            params["pageToken"] = data["nextPageToken"]
        else:
            break
    return files

async def delete_file(client, file_id):
    token = await get_token(client)
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    params = {"supportsAllDrives": "true"}
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete(url, params=params, headers=headers)
    return resp.status_code == 204

async def clean_recursively(client, folder_id, is_target_branch):
    deleted = 0
    files = await list_files(client, folder_id)
    for f in files:
        if f["mimeType"] == "application/vnd.google-apps.folder":
            # If we are in the target branch, all subfolders are part of the target branch
            is_now_target = is_target_branch or (f["name"] in ["02_Company", "03_Tax"])
            deleted += await clean_recursively(client, f["id"], is_now_target)
        elif f["mimeType"] == "application/vnd.google-apps.shortcut":
            if is_target_branch:
                print(f"Deleting shortcut: {f['name']}")
                if await delete_file(client, f["id"]):
                    deleted += 1
    return deleted

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        deleted = await clean_recursively(client, ARIANNA_DRIVE_ID, False)
        print(f"Done. Deleted {deleted} shortcuts.")

if __name__ == "__main__":
    asyncio.run(main())
