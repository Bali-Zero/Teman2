"""
NUZANTARA - Continuous Dropbox → Google Drive Sync
===================================================

Monitors Dropbox for new files and auto-migrates to Google Drive + CRM

Run this as a background service:
  python continuous_sync_watcher.py &

Author: Zero (with Claude)
"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Set, Dict
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('continuous_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DropboxWatcher:
    """Watch Dropbox for new/modified files"""
    
    def __init__(self, watch_path: str, check_interval: int = 60):
        self.watch_path = watch_path
        self.check_interval = check_interval  # seconds
        self.known_files: Set[str] = set()
        self.file_hashes: Dict[str, str] = {}
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return ""
    
    def scan_directory(self) -> Set[str]:
        """Scan directory and return set of all file paths"""
        files = set()
        try:
            for root, dirs, filenames in os.walk(self.watch_path):
                # Skip excluded folders
                dirs[:] = [d for d in dirs if d not in {'.', '..', 'cache', 'temp'}]
                
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    files.add(file_path)
        except Exception as e:
            logger.error(f"Error scanning directory: {e}")
        
        return files
    
    def detect_changes(self) -> Dict[str, list]:
        """
        Detect new and modified files
        Returns: {'new': [...], 'modified': [...]}
        """
        current_files = self.scan_directory()
        
        new_files = current_files - self.known_files
        modified_files = []
        
        # Check for modifications in existing files
        for file_path in current_files & self.known_files:
            current_hash = self.get_file_hash(file_path)
            if current_hash and current_hash != self.file_hashes.get(file_path):
                modified_files.append(file_path)
                self.file_hashes[file_path] = current_hash
        
        # Update known files
        self.known_files = current_files
        
        # Update hashes for new files
        for file_path in new_files:
            self.file_hashes[file_path] = self.get_file_hash(file_path)
        
        return {
            'new': list(new_files),
            'modified': modified_files
        }
    
    def watch(self, callback):
        """
        Continuous monitoring loop
        
        Args:
            callback: Function to call with detected changes
        """
        logger.info(f"Starting Dropbox watcher: {self.watch_path}")
        logger.info(f"Check interval: {self.check_interval}s")
        
        # Initial scan
        self.known_files = self.scan_directory()
        logger.info(f"Initial scan: {len(self.known_files)} files")
        
        while True:
            try:
                changes = self.detect_changes()
                
                if changes['new'] or changes['modified']:
                    logger.info(f"Detected changes: {len(changes['new'])} new, {len(changes['modified'])} modified")
                    callback(changes)
                
                time.sleep(self.check_interval)
            
            except KeyboardInterrupt:
                logger.info("Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                time.sleep(self.check_interval)


def process_new_files(changes: Dict):
    """
    Process detected file changes
    
    This is called by the watcher when new files are detected
    """
    for file_path in changes['new']:
        logger.info(f"New file detected: {file_path}")
        
        # TODO: Call migration logic
        # 1. Categorize document
        # 2. Upload to Google Drive
        # 3. Update CRM database
        # 4. Send notification (optional)
    
    for file_path in changes['modified']:
        logger.info(f"Modified file: {file_path}")
        # TODO: Handle file modifications


def main():
    """Main entry point for continuous sync"""
    
    DROPBOX_PATH = os.getenv("DROPBOX_WATCH_PATH", "/path/to/dropbox")
    
    if not os.path.exists(DROPBOX_PATH):
        logger.error(f"Dropbox path not found: {DROPBOX_PATH}")
        logger.info("Set DROPBOX_WATCH_PATH environment variable")
        return
    
    watcher = DropboxWatcher(
        watch_path=DROPBOX_PATH,
        check_interval=60  # Check every minute
    )
    
    watcher.watch(callback=process_new_files)


if __name__ == "__main__":
    main()
