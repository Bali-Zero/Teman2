import asyncio, asyncpg, httpx

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"
INDIVIDUAL_CRM_ID = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"

async def main():
    conn = await asyncpg.connect("postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:5555/nuzantara_rag?sslmode=disable")

    rows = await conn.fetch("""
        SELECT id, google_drive_folder_id FROM clients_archive
        WHERE google_drive_folder_id IS NOT NULL AND google_drive_folder_id != ''
    """)
    print(f"Archived clients with Drive folder: {len(rows)}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": OAUTH_CLIENT_ID, "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN, "grant_type": "refresh_token",
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Find parent of Individual_CRM
        r = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{INDIVIDUAL_CRM_ID}",
            headers=headers, params={"supportsAllDrives": "true", "fields": "parents"},
        )
        parent_id = r.json().get("parents", ["root"])[0]

        # Check/create Archive_CRM
        r = await client.get("https://www.googleapis.com/drive/v3/files", headers=headers, params={
            "q": f"'{parent_id}' in parents and name = 'Archive_CRM' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name)",
        })
        existing = r.json().get("files", [])

        if existing:
            archive_id = existing[0]["id"]
            print(f"Archive_CRM exists: {archive_id}")
        else:
            r = await client.post("https://www.googleapis.com/drive/v3/files", headers=headers,
                params={"supportsAllDrives": "true"},
                json={"name": "Archive_CRM", "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]})
            archive_id = r.json()["id"]
            print(f"Created Archive_CRM: {archive_id}")

        # Move folders
        moved = 0
        errors = 0
        for i, row in enumerate(rows):
            folder_id = row["google_drive_folder_id"]
            try:
                r = await client.patch(
                    f"https://www.googleapis.com/drive/v3/files/{folder_id}",
                    headers=headers,
                    params={
                        "addParents": archive_id,
                        "removeParents": INDIVIDUAL_CRM_ID,
                        "supportsAllDrives": "true",
                    },
                )
                if r.status_code == 200:
                    moved += 1
                else:
                    errors += 1
                    if errors <= 3:
                        print(f"  Error {r.status_code}: {r.text[:80]}")
            except Exception as e:
                errors += 1

            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(rows)} moved={moved} errors={errors}")

        print(f"\nMoved to Archive_CRM: {moved}")
        print(f"Errors: {errors}")

    await conn.close()

asyncio.run(main())
