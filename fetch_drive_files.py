import httpx
import json
import os

BACKEND_URL = "https://nuzantara-rag.fly.dev"
API_KEY = os.getenv("NUZ_API_KEY", "fba3cdca-5ef2-484d-a423-edecfde23a43")
FOLDER_ID = "1jcLQ6slWAeQupE8jQjp4EFjAfwlNfteM"

def fetch_all_files(folder_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-API-Key": API_KEY
    }
    
    all_files = []
    page_token = None
    
    while True:
        params = {
            "folder_id": folder_id,
            "page_size": 50
        }
        if page_token:
            params["page_token"] = page_token
            
        print(f"Fetching page with token: {page_token}")
        response = httpx.get(f"{BACKEND_URL}/api/drive/files", params=params, headers=headers, timeout=120.0)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            break
            
        data = response.json()
        files = data.get("files", [])
        all_files.extend(files)
        print(f"Retrieved {len(files)} files. Total so far: {len(all_files)}")
        
        page_token = data.get("next_page_token")
        if not page_token:
            break
            
    return all_files

if __name__ == "__main__":
    files = fetch_all_files(FOLDER_ID)
    with open("all_drive_files.json", "w") as f:
        json.dump(files, f, indent=2)
    print(f"Done. Total files: {len(files)}")
