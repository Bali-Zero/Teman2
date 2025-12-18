#!/usr/bin/env python3
"""
NUZANTARA PRIME - Dependency Watcher (24/7)
Monitors dependencies for security vulnerabilities and updates.
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class DependencyWatcher:
    """Monitors and manages dependencies"""

    def __init__(self):
        self.backend_path = Path(__file__).parent.parent
        self.requirements_file = self.backend_path / "requirements.txt"

    async def check_security_vulnerabilities(self) -> dict[str, Any]:
        """Check for known security vulnerabilities"""
        logger.info("🔒 Checking for security vulnerabilities...")

        try:
            result = subprocess.run(
                ["pip-audit", "--requirement", str(self.requirements_file), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                vulnerabilities = json.loads(result.stdout) if result.stdout else []
                return {
                    "status": "ok",
                    "vulnerabilities": vulnerabilities,
                    "count": len(vulnerabilities),
                }
            else:
                return {
                    "status": "error",
                    "message": result.stderr,
                }
        except FileNotFoundError:
            logger.warning("⚠️  pip-audit not installed. Install with: pip install pip-audit")
            return {"status": "skipped", "message": "pip-audit not available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def check_outdated_packages(self) -> dict[str, Any]:
        """Check for outdated packages"""
        logger.info("📦 Checking for outdated packages...")

        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                outdated = json.loads(result.stdout) if result.stdout else []
                # Filter to only packages in requirements.txt
                requirements = self.requirements_file.read_text().split("\n")
                req_packages = {
                    line.split("==")[0].split(">=")[0].split("~=")[0].strip().lower()
                    for line in requirements
                    if line.strip() and not line.startswith("#")
                }

                outdated_relevant = [
                    pkg for pkg in outdated
                    if pkg["name"].lower() in req_packages
                ]

                return {
                    "status": "ok",
                    "outdated": outdated_relevant,
                    "count": len(outdated_relevant),
                }
            else:
                return {"status": "error", "message": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def generate_update_pr(self) -> str:
        """Generate PR description for dependency updates"""
        vulnerabilities = await self.check_security_vulnerabilities()
        outdated = await self.check_outdated_packages()

        pr_body = []
        pr_body.append("# 🔄 Dependency Update PR")
        pr_body.append("")
        pr_body.append("## Security Vulnerabilities")
        if vulnerabilities.get("count", 0) > 0:
            pr_body.append(f"⚠️  **{vulnerabilities['count']} vulnerabilities found**")
            for vuln in vulnerabilities.get("vulnerabilities", [])[:10]:
                pr_body.append(f"- {vuln.get('name', 'unknown')}: {vuln.get('vuln', 'unknown')}")
        else:
            pr_body.append("✅ No known vulnerabilities")

        pr_body.append("")
        pr_body.append("## Outdated Packages")
        if outdated.get("count", 0) > 0:
            pr_body.append(f"📦 **{outdated['count']} packages outdated**")
            for pkg in outdated.get("outdated", [])[:10]:
                pr_body.append(f"- {pkg.get('name', 'unknown')}: {pkg.get('version', '?')} → {pkg.get('latest_version', '?')}")
        else:
            pr_body.append("✅ All packages up to date")

        return "\n".join(pr_body)

    async def run_check(self) -> None:
        """Run dependency checks"""
        print("=" * 70)
        print("NUZANTARA PRIME - DEPENDENCY WATCHER")
        print("=" * 70)

        vulnerabilities = await self.check_security_vulnerabilities()
        outdated = await self.check_outdated_packages()

        print("\n📊 RESULTS:")
        print(f"  Security Vulnerabilities: {vulnerabilities.get('count', 0)}")
        print(f"  Outdated Packages: {outdated.get('count', 0)}")

        if vulnerabilities.get("count", 0) > 0 or outdated.get("count", 0) > 0:
            print("\n⚠️  Action required: Review and update dependencies")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Dependency Watcher")
    parser.add_argument("--pr", action="store_true", help="Generate PR description")

    args = parser.parse_args()

    watcher = DependencyWatcher()

    if args.pr:
        pr_body = asyncio.run(watcher.generate_update_pr())
        print(pr_body)
    else:
        asyncio.run(watcher.run_check())


if __name__ == "__main__":
    main()


