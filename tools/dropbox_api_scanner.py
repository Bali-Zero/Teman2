#!/usr/bin/env python3
"""
Dropbox API Scanner

Scans Dropbox via API (cloud-based, no local files needed).
Useful when files are not on local machine.

Requirements:
    pip install dropbox

Setup:
    1. Get Dropbox access token:
       - Go to https://www.dropbox.com/developers/apps
       - Create app or use existing
       - Generate access token
    2. Run script with token:
       python3 dropbox_api_scanner.py --token YOUR_TOKEN

Usage:
    python3 dropbox_api_scanner.py --token YOUR_TOKEN --output inventory.json
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

try:
    import dropbox
    from dropbox.exceptions import ApiError, AuthError
except ImportError:
    print("❌ Error: 'dropbox' module not installed")
    print("Install with: pip install dropbox")
    sys.exit(1)


class DropboxAPIScanner:
    """Scans Dropbox using API"""

    def __init__(self, access_token: str, verbose: bool = True):
        self.dbx = dropbox.Dropbox(access_token)
        self.verbose = verbose
        self.inventory = {
            "scan_date": datetime.now().isoformat(),
            "scan_method": "dropbox_api",
            "summary": {},
            "folders": {},
            "statistics": {},
        }

    def log(self, message: str, level: str = "INFO"):
        """Log message"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix = {
                "INFO": "  ℹ️",
                "SUCCESS": "✅",
                "ERROR": "❌",
                "WARN": "⚠️",
                "SCAN": "🔍",
            }.get(level, "ℹ️")
            print(f"[{timestamp}] {prefix} {message}")

    def test_connection(self) -> bool:
        """Test Dropbox API connection"""
        self.log("Testing Dropbox API connection...", "SCAN")
        try:
            account = self.dbx.users_get_current_account()
            self.log(
                f"Connected to: {account.name.display_name} ({account.email})",
                "SUCCESS",
            )
            return True
        except AuthError as e:
            self.log(f"Authentication failed: {e}", "ERROR")
            return False
        except Exception as e:
            self.log(f"Connection test failed: {e}", "ERROR")
            return False

    def scan_folder(
        self, path: str = "", max_depth: int = 3, current_depth: int = 0
    ) -> Dict[str, Any]:
        """
        Recursively scan a Dropbox folder via API.

        Args:
            path: Dropbox path (empty string = root)
            max_depth: Maximum recursion depth
            current_depth: Current depth (internal use)

        Returns:
            Folder info dictionary
        """
        info = {
            "path": path or "/",
            "name": path.split("/")[-1] if path else "Root",
            "file_count": 0,
            "total_size": 0,
            "subfolder_count": 0,
            "subfolders": {},
            "file_types": defaultdict(int),
            "largest_files": [],
        }

        try:
            # List folder contents
            result = self.dbx.files_list_folder(path)

            entries = result.entries

            # Handle pagination (if more than 2000 entries)
            while result.has_more:
                result = self.dbx.files_list_folder_continue(result.cursor)
                entries.extend(result.entries)

            for entry in entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    # File
                    info["file_count"] += 1
                    info["total_size"] += entry.size

                    # Track file type
                    ext = (
                        ("." + entry.name.split(".")[-1]).lower()
                        if "." in entry.name
                        else "[no extension]"
                    )
                    info["file_types"][ext] += 1

                    # Track largest files
                    info["largest_files"].append(
                        {
                            "name": entry.name,
                            "size": entry.size,
                            "path": entry.path_display,
                        }
                    )

                elif isinstance(entry, dropbox.files.FolderMetadata):
                    # Subfolder
                    info["subfolder_count"] += 1

                    # Recurse if not at max depth
                    if current_depth < max_depth:
                        self.log(f"Scanning: {entry.path_display}", "SCAN")
                        subfolder_info = self.scan_folder(
                            entry.path_display, max_depth, current_depth + 1
                        )
                        info["subfolders"][entry.name] = subfolder_info

                        # Accumulate stats from children
                        info["file_count"] += subfolder_info["file_count"]
                        info["total_size"] += subfolder_info["total_size"]
                        info["subfolder_count"] += subfolder_info["subfolder_count"]

            # Sort largest files
            info["largest_files"] = sorted(
                info["largest_files"], key=lambda x: x["size"], reverse=True
            )[:10]

            # Convert defaultdict to dict
            info["file_types"] = dict(info["file_types"])

        except ApiError as e:
            self.log(f"API Error scanning {path}: {e}", "ERROR")
            info["error"] = str(e)

        return info

    def scan_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """Scan entire Dropbox structure"""
        self.log("Starting Dropbox scan via API...", "SCAN")
        self.log(f"Max depth: {max_depth}", "INFO")

        # Scan root
        root_info = self.scan_folder("", max_depth)

        # Store in inventory
        self.inventory["root"] = root_info

        # Generate summary
        self._generate_summary()

        return self.inventory

    def _generate_summary(self):
        """Generate summary statistics"""
        root = self.inventory.get("root", {})

        self.inventory["summary"] = {
            "total_files": root.get("file_count", 0),
            "total_size_bytes": root.get("total_size", 0),
            "total_size_gb": round(root.get("total_size", 0) / (1024**3), 2),
            "total_folders": root.get("subfolder_count", 0),
            "file_types": root.get("file_types", {}),
        }

        # Top file types
        file_types = root.get("file_types", {})
        sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)

        self.inventory["statistics"] = {
            "top_file_types": sorted_types[:10],
            "total_unique_extensions": len(file_types),
        }

    def identify_client_folders(self) -> List[Dict[str, Any]]:
        """Identify potential client folders"""
        self.log("Identifying client folders...", "SCAN")

        client_folders = []
        root = self.inventory.get("root", {})

        # Look for INDIVIDUALS and COMPANIES folders
        for folder_name, folder_info in root.get("subfolders", {}).items():
            if folder_name.upper() in ["INDIVIDUALS", "COMPANIES"]:
                folder_type = (
                    "individual" if "INDIVIDUAL" in folder_name.upper() else "company"
                )

                # Each subfolder is likely a client
                for client_name, client_info in folder_info.get(
                    "subfolders", {}
                ).items():
                    client_folders.append(
                        {
                            "folder_name": client_name,
                            "type": folder_type,
                            "file_count": client_info["file_count"],
                            "total_size": client_info["total_size"],
                            "path": client_info["path"],
                        }
                    )

        self.log(f"Found {len(client_folders)} potential client folders", "SUCCESS")
        return client_folders

    def save_inventory(self, output_path: str):
        """Save inventory to JSON"""
        with open(output_path, "w") as f:
            json.dump(self.inventory, f, indent=2)
        self.log(f"Inventory saved to: {output_path}", "SUCCESS")

    def print_summary(self):
        """Print summary"""
        print("\n" + "=" * 70)
        print("📊 DROPBOX API SCAN SUMMARY")
        print("=" * 70)

        summary = self.inventory["summary"]

        print(f"\n📁 Total Folders: {summary['total_folders']:,}")
        print(f"📄 Total Files: {summary['total_files']:,}")
        print(
            f"💾 Total Size: {summary['total_size_gb']:.2f} GB ({summary['total_size_bytes']:,} bytes)"
        )

        print(
            f"\n📋 File Types: {self.inventory['statistics']['total_unique_extensions']} unique extensions"
        )
        for ext, count in self.inventory["statistics"]["top_file_types"][:5]:
            print(f"  • {ext}: {count:,} files")

        print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Scan Dropbox via API")
    parser.add_argument("--token", required=True, help="Dropbox access token")
    parser.add_argument(
        "--output", default="dropbox_api_inventory.json", help="Output JSON file"
    )
    parser.add_argument(
        "--depth", type=int, default=3, help="Max scan depth (default: 3)"
    )
    parser.add_argument("--quiet", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    print("\n🔍 Starting Dropbox API Scanner...")
    print(f"   Depth: {args.depth}")
    print(f"   Output: {args.output}\n")

    # Create scanner
    scanner = DropboxAPIScanner(args.token, verbose=not args.quiet)

    # Test connection
    if not scanner.test_connection():
        print("\n❌ Failed to connect to Dropbox API")
        print("Check your access token and try again.")
        sys.exit(1)

    # Scan structure
    scanner.scan_structure(max_depth=args.depth)

    # Identify clients
    client_folders = scanner.identify_client_folders()
    scanner.inventory["client_folders"] = client_folders

    # Save
    scanner.save_inventory(args.output)

    # Print summary
    scanner.print_summary()

    print(f"✅ Scan complete! Inventory saved to: {args.output}\n")


if __name__ == "__main__":
    main()
