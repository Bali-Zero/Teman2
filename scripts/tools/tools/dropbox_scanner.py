#!/usr/bin/env python3
"""
Dropbox Structure Scanner

Analyzes Dropbox folder structure for CRM migration.
Scans ~450GB of client documents and generates inventory.

Usage:
    python3 dropbox_scanner.py --dropbox-path ~/Dropbox/ --output inventory.json
    python3 dropbox_scanner.py --quick-scan  # Fast overview
    python3 dropbox_scanner.py --full-scan   # Deep analysis

Features:
- Scans folder structure
- Counts files and calculates sizes
- Identifies client folders
- Categorizes documents
- Generates migration inventory
"""

import os
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict

# Add backend to path for categorization
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../apps/backend-rag"))


class DropboxScanner:
    """Scans Dropbox structure and generates migration inventory"""

    def __init__(self, dropbox_path: str, verbose: bool = True):
        self.dropbox_path = Path(dropbox_path).expanduser().resolve()
        self.verbose = verbose
        self.inventory = {
            "scan_date": datetime.now().isoformat(),
            "dropbox_path": str(self.dropbox_path),
            "summary": {},
            "folders": {},
            "statistics": {},
        }

    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose"""
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

    def scan_folder_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """
        Scan folder structure with configurable depth.

        Args:
            max_depth: Maximum depth to scan (1=top level only, 3=default)

        Returns:
            Dictionary with folder structure
        """
        self.log(f"Scanning Dropbox at: {self.dropbox_path}", "SCAN")

        if not self.dropbox_path.exists():
            self.log(f"Dropbox path does not exist: {self.dropbox_path}", "ERROR")
            return {}

        # Scan top-level folders
        top_level_folders = []

        try:
            for item in sorted(self.dropbox_path.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    top_level_folders.append(item.name)
                    self.log(f"Found top-level folder: {item.name}", "INFO")
        except PermissionError as e:
            self.log(f"Permission denied: {e}", "ERROR")
            return {}

        # Analyze each top-level folder
        for folder_name in top_level_folders:
            folder_path = self.dropbox_path / folder_name
            self.log(f"Analyzing: {folder_name}...", "SCAN")

            folder_info = self._analyze_folder(
                folder_path, current_depth=1, max_depth=max_depth
            )
            self.inventory["folders"][folder_name] = folder_info

        # Generate summary
        self._generate_summary()

        return self.inventory

    def _analyze_folder(
        self, folder_path: Path, current_depth: int = 1, max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Recursively analyze a folder.

        Returns folder info with file counts, sizes, and structure.
        """
        info = {
            "path": str(folder_path),
            "name": folder_path.name,
            "file_count": 0,
            "total_size": 0,
            "subfolder_count": 0,
            "subfolders": {},
            "file_types": defaultdict(int),
            "largest_files": [],
        }

        try:
            items = list(folder_path.iterdir())

            for item in items:
                # Skip hidden files/folders
                if item.name.startswith("."):
                    continue

                if item.is_file():
                    # Count file
                    info["file_count"] += 1

                    # Get file size
                    try:
                        file_size = item.stat().st_size
                        info["total_size"] += file_size

                        # Track file type
                        ext = item.suffix.lower()
                        if ext:
                            info["file_types"][ext] += 1
                        else:
                            info["file_types"]["[no extension]"] += 1

                        # Track largest files (top 5)
                        info["largest_files"].append(
                            {"name": item.name, "size": file_size, "extension": ext}
                        )

                    except (OSError, PermissionError):
                        self.log(f"Cannot access file: {item}", "WARN")

                elif item.is_dir():
                    info["subfolder_count"] += 1

                    # Recurse if not at max depth
                    if current_depth < max_depth:
                        subfolder_info = self._analyze_folder(
                            item, current_depth + 1, max_depth
                        )
                        info["subfolders"][item.name] = subfolder_info

                        # Accumulate child stats
                        info["file_count"] += subfolder_info["file_count"]
                        info["total_size"] += subfolder_info["total_size"]
                        info["subfolder_count"] += subfolder_info["subfolder_count"]

            # Sort largest files by size (keep top 5)
            info["largest_files"] = sorted(
                info["largest_files"], key=lambda x: x["size"], reverse=True
            )[:5]

            # Convert defaultdict to regular dict for JSON serialization
            info["file_types"] = dict(info["file_types"])

        except PermissionError:
            self.log(f"Permission denied: {folder_path}", "WARN")
            info["error"] = "Permission denied"

        return info

    def _generate_summary(self):
        """Generate overall summary statistics"""
        total_files = 0
        total_size = 0
        total_folders = 0
        all_file_types = defaultdict(int)

        for folder_name, folder_info in self.inventory["folders"].items():
            total_files += folder_info["file_count"]
            total_size += folder_info["total_size"]
            total_folders += folder_info["subfolder_count"] + 1  # +1 for folder itself

            # Aggregate file types
            for ext, count in folder_info["file_types"].items():
                all_file_types[ext] += count

        self.inventory["summary"] = {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
            "total_folders": total_folders,
            "top_level_folders": len(self.inventory["folders"]),
            "file_types": dict(all_file_types),
        }

        # Sort file types by count
        sorted_types = sorted(all_file_types.items(), key=lambda x: x[1], reverse=True)
        self.inventory["statistics"] = {
            "top_file_types": sorted_types[:10],
            "total_unique_extensions": len(all_file_types),
        }

    def identify_client_folders(self) -> List[Dict[str, Any]]:
        """
        Identify folders that likely contain client data.

        Returns list of potential client folders with metadata.
        """
        self.log("Identifying potential client folders...", "SCAN")

        client_folders = []

        # Check INDIVIDUALS and COMPANIES folders
        for top_level in ["INDIVIDUALS", "COMPANIES", "Individuals", "Companies"]:
            if top_level in self.inventory["folders"]:
                folder_info = self.inventory["folders"][top_level]

                # Each subfolder is likely a client
                for subfolder_name, subfolder_info in folder_info.get(
                    "subfolders", {}
                ).items():
                    client_folders.append(
                        {
                            "folder_name": subfolder_name,
                            "type": "individual"
                            if "individual" in top_level.lower()
                            else "company",
                            "file_count": subfolder_info["file_count"],
                            "total_size": subfolder_info["total_size"],
                            "path": subfolder_info["path"],
                        }
                    )

        self.log(f"Found {len(client_folders)} potential client folders", "SUCCESS")

        return client_folders

    def categorize_files(self) -> Dict[str, Any]:
        """
        Categorize all files using the CRM categorization service.

        Returns categorization statistics.
        """
        self.log("Categorizing files...", "SCAN")

        try:
            from backend.services.crm.document_categorizer import (
                auto_categorize_document,
                get_categorization_stats,
            )

            all_categorizations = []

            # Collect all filenames
            def collect_files(folder_info):
                """Recursively collect files"""
                files = []

                # Get files from current folder
                if "path" in folder_info:
                    try:
                        folder_path = Path(folder_info["path"])
                        if folder_path.exists():
                            for item in folder_path.iterdir():
                                if item.is_file() and not item.name.startswith("."):
                                    files.append(item.name)
                    except (PermissionError, OSError):
                        pass

                # Recurse into subfolders
                for subfolder_info in folder_info.get("subfolders", {}).values():
                    files.extend(collect_files(subfolder_info))

                return files

            # Categorize files from each top-level folder
            for folder_name, folder_info in self.inventory["folders"].items():
                files = collect_files(folder_info)
                self.log(
                    f"Categorizing {len(files)} files from {folder_name}...", "INFO"
                )

                for filename in files:
                    cat_result = auto_categorize_document(filename)
                    all_categorizations.append(cat_result)

            # Get statistics
            stats = get_categorization_stats(all_categorizations)

            self.log(f"Categorized {stats['total']} files", "SUCCESS")
            self.log(f"Average confidence: {stats['avg_confidence']:.2f}", "INFO")
            self.log(f"Uncategorized: {stats['uncategorized']}", "INFO")

            return stats

        except ImportError as e:
            self.log(f"Cannot import categorization service: {e}", "WARN")
            return {}

    def save_inventory(self, output_path: str):
        """Save inventory to JSON file"""
        output_path = Path(output_path).expanduser().resolve()

        with open(output_path, "w") as f:
            json.dump(self.inventory, f, indent=2)

        self.log(f"Inventory saved to: {output_path}", "SUCCESS")

    def print_summary(self):
        """Print summary to console"""
        print("\n" + "=" * 70)
        print("📊 DROPBOX SCAN SUMMARY")
        print("=" * 70)

        summary = self.inventory["summary"]

        print(f"\n📁 Total Folders: {summary['total_folders']:,}")
        print(f"📄 Total Files: {summary['total_files']:,}")
        print(
            f"💾 Total Size: {summary['total_size_gb']:.2f} GB ({summary['total_size_bytes']:,} bytes)"
        )

        print(f"\n📂 Top-Level Folders: {summary['top_level_folders']}")
        for folder_name in self.inventory["folders"].keys():
            folder_info = self.inventory["folders"][folder_name]
            print(
                f"  • {folder_name}: {folder_info['file_count']:,} files ({folder_info['total_size'] / (1024**3):.2f} GB)"
            )

        print(
            f"\n📋 File Types: {self.inventory['statistics']['total_unique_extensions']} unique extensions"
        )
        for ext, count in self.inventory["statistics"]["top_file_types"][:5]:
            print(f"  • {ext}: {count:,} files")

        print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Scan Dropbox structure for CRM migration"
    )
    parser.add_argument(
        "--dropbox-path",
        default="~/Dropbox/",
        help="Path to Dropbox folder (default: ~/Dropbox/)",
    )
    parser.add_argument(
        "--output",
        default="dropbox_inventory.json",
        help="Output JSON file (default: dropbox_inventory.json)",
    )
    parser.add_argument(
        "--quick-scan", action="store_true", help="Quick scan (depth=1, top-level only)"
    )
    parser.add_argument(
        "--full-scan",
        action="store_true",
        help="Full deep scan (depth=5, may take longer)",
    )
    parser.add_argument(
        "--categorize",
        action="store_true",
        help="Categorize all files (slower but more detailed)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Quiet mode (minimal output)"
    )

    args = parser.parse_args()

    # Determine scan depth
    if args.quick_scan:
        depth = 1
    elif args.full_scan:
        depth = 5
    else:
        depth = 3  # Default

    print("\n🔍 Starting Dropbox Scan...")
    print(f"   Path: {args.dropbox_path}")
    print(f"   Depth: {depth}")
    print(f"   Output: {args.output}")
    print()

    # Create scanner
    scanner = DropboxScanner(args.dropbox_path, verbose=not args.quiet)

    # Scan structure
    scanner.scan_folder_structure(max_depth=depth)

    # Identify client folders
    client_folders = scanner.identify_client_folders()
    scanner.inventory["client_folders"] = client_folders

    # Categorize files (optional)
    if args.categorize:
        cat_stats = scanner.categorize_files()
        scanner.inventory["categorization_stats"] = cat_stats

    # Save inventory
    scanner.save_inventory(args.output)

    # Print summary
    scanner.print_summary()

    print(f"✅ Scan complete! Inventory saved to: {args.output}")


if __name__ == "__main__":
    main()
