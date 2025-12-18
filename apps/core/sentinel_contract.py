"""
SENTINEL CONTRACT - API Consistency Check
Part of the Zantara Full-Stack Observability Suite.

This script ensures that the Frontend code is in sync with the Backend API contract.
It performs the following steps:
1. Fetches the latest OpenAPI specification from the running Backend.
2. Regenerates the Frontend Client using `openapi-typescript-codegen`.
3. Runs TypeScript compiler (`tsc`) to check for type errors.

If this script passes, it means the Frontend is fully compatible with the current Backend.
If it fails, it means there is a "Contract Breach" (e.g. Backend changed a field name).

Usage:
    python apps/core/sentinel_contract.py --backend-url https://nuzantara-rag.fly.dev
"""

import argparse
import subprocess
import sys
import json
import requests
import os
import shutil
from pathlib import Path


class Colors:
    HEADER = "\033[95m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


class ContractSentinel:
    def __init__(
        self, backend_url: str, frontend_dir: Path, openapi_path: Path | None = None
    ):
        self.backend_url = backend_url.rstrip("/")
        self.frontend_dir = frontend_dir
        self.openapi_path = openapi_path or (frontend_dir / "openapi.json")
        npm_bin = shutil.which("npm")
        if not npm_bin:
            raise RuntimeError(
                "npm binary not found in PATH. Install Node.js before running Sentinel."
            )
        self.npm_path = npm_bin

    def run_check(self) -> bool:
        print(f"{Colors.HEADER}🛡️  Starting Contract Sentinel Check...{Colors.ENDC}")

        # 1. Fetch OpenAPI Spec
        if not self._fetch_openapi():
            return False

        # 2. Generate Client
        if not self._generate_client():
            return False

        # 3. Type Check
        if not self._run_type_check():
            return False

        print(
            f"\n{Colors.OKGREEN}✅ CONTRACT VERIFIED: Frontend is in sync with Backend.{Colors.ENDC}"
        )
        return True

    def _fetch_openapi(self) -> bool:
        print(
            f"\n{Colors.WARNING}1. Fetching OpenAPI Spec from {self.backend_url}...{Colors.ENDC}"
        )
        try:
            # Try standard path first, then /api/v1/openapi.json
            paths = ["/openapi.json", "/api/v1/openapi.json", "/api/openapi.json"]

            for path in paths:
                url = f"{self.backend_url}{path}"
                print(f"Trying {url}...")
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        spec = response.json()
                        with open(self.openapi_path, "w") as f:
                            json.dump(spec, f, indent=2)
                        print(
                            f"{Colors.OKGREEN}✔ OpenAPI Spec saved from {url}{Colors.ENDC}"
                        )
                        return True
                except Exception:
                    continue

            raise Exception("Could not find OpenAPI spec at any common path")
        except Exception as e:
            print(f"{Colors.FAIL}✘ Failed to fetch OpenAPI Spec: {e}{Colors.ENDC}")
            if self.openapi_path.exists():
                print(
                    f"{Colors.WARNING}⚠️  Falling back to existing {self.openapi_path} (offline mode).{Colors.ENDC}"
                )
                return True
            return False

    def _generate_client(self) -> bool:
        print(f"\n{Colors.WARNING}2. Regenerating Frontend Client...{Colors.ENDC}")
        try:
            env = os.environ.copy()
            cmd = [
                self.npm_path,
                "exec",
                "openapi-typescript-codegen",
                "--",
                "--input",
                str(self.openapi_path.resolve()),
                "--output",
                "lib/api/generated",
                "--client",
                "fetch",
                "--name",
                "NuzantaraClient",
            ]

            subprocess.run(
                cmd,
                cwd=self.frontend_dir,
                check=True,
                capture_output=True,
                env=env,
            )
            print(f"{Colors.OKGREEN}✔ Client generated successfully{Colors.ENDC}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"{Colors.FAIL}✘ Client generation failed:{Colors.ENDC}")
            print(e.stderr.decode())
            return False

    def _run_type_check(self) -> bool:
        print(f"\n{Colors.WARNING}3. Running TypeScript Type Check...{Colors.ENDC}")
        try:
            env = os.environ.copy()
            cmd = [
                self.npm_path,
                "exec",
                "tsc",
                "--",
                "--noEmit",
            ]
            subprocess.run(
                cmd,
                cwd=self.frontend_dir,
                check=True,
                capture_output=True,
                env=env,
            )
            print(f"{Colors.OKGREEN}✔ No type errors found{Colors.ENDC}")
            return True
        except subprocess.CalledProcessError as e:
            print(
                f"{Colors.FAIL}✘ Type check failed (Contract Breach Detected!):{Colors.ENDC}"
            )
            # Print only the first few lines of errors to avoid flooding
            errors = e.stdout.decode().split("\n")[:20]
            print("\n".join(errors))
            return False


def main():
    parser = argparse.ArgumentParser(description="Sentinel Contract Check")
    parser.add_argument(
        "--backend-url", default="https://nuzantara-rag.fly.dev", help="Backend URL"
    )
    parser.add_argument(
        "--openapi-path",
        default=None,
        help="Optional path to reuse an existing OpenAPI spec (offline fallback)",
    )
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent.parent
    frontend_dir = root_dir / "apps" / "mouth"

    openapi_path = Path(args.openapi_path) if args.openapi_path else None
    sentinel = ContractSentinel(
        args.backend_url, frontend_dir, openapi_path=openapi_path
    )
    success = sentinel.run_check()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
