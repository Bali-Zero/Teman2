#!/usr/bin/env python3
"""
Download file from Google Drive by File ID
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

load_dotenv()

def download_file_from_drive(file_id: str, output_path: Path):
    """Download file from Google Drive using Service Account"""
    
    # Get credentials
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        print("❌ GOOGLE_CREDENTIALS_JSON not found in environment")
        return False
    
    try:
        # Parse credentials
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        
        # Build Drive service
        service = build("drive", "v3", credentials=creds)
        
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields="name, mimeType, size").execute()
        file_name = file_metadata.get("name", f"file_{file_id}")
        file_size = int(file_metadata.get("size", 0))
        
        print(f"📁 File: {file_name}")
        print(f"📊 Size: {file_size / (1024*1024):.2f} MB")
        print(f"💾 Downloading to: {output_path}")
        
        # Download file
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"   Progress: {progress}%", end="\r")
        
        print(f"\n✅ Download complete!")
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(fh.getvalue())
        
        print(f"✅ Saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/download_drive_file.py <file_id> [output_path]")
        print("\nExample:")
        print("  python scripts/download_drive_file.py 1Lx4y9TQ45uBUyvNzeHiHinxo_k_WOMmm")
        sys.exit(1)
    
    file_id = sys.argv[1]
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"apps/scraper/data/raw_laws_local/drive_file_{file_id}.zip")
    
    print("🚀 Downloading file from Google Drive...")
    print(f"   File ID: {file_id}")
    print(f"   Output: {output_path}\n")
    
    success = download_file_from_drive(file_id, output_path)
    
    if success:
        print(f"\n✅ File downloaded successfully!")
        print(f"💡 Next step: Extract and ingest the file")
    else:
        print(f"\n❌ Download failed")
        sys.exit(1)

