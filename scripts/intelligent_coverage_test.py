#!/usr/bin/env python3
"""
Intelligent Coverage Test Generator using Ollama Qwen
Uses local Qwen LLM to analyze codebase and generate comprehensive test coverage
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List

import httpx

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag" / "backend"
TESTS_DIR = BACKEND_DIR / "tests"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:latest"


class IntelligentCoverageGenerator:
    """Uses Ollama Qwen to intelligently generate test coverage"""

    def __init__(self):
        self.ollama_available = False
        self._check_ollama()

    def _check_ollama(self):
        """Check if Ollama is available"""
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{OLLAMA_URL}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    self.ollama_available = any(
                        OLLAMA_MODEL in name or name in OLLAMA_MODEL
                        for name in model_names
                    )
                    if self.ollama_available:
                        print(f"✅ Ollama available with model: {OLLAMA_MODEL}")
                    else:
                        print(f"⚠️  Ollama available but model {OLLAMA_MODEL} not found")
                        print(f"   Available models: {', '.join(model_names[:5])}")
        except Exception as e:
            print(f"⚠️  Ollama not available: {e}")
            self.ollama_available = False

    def _call_qwen(self, prompt: str, system_prompt: str = None) -> str:
        """Call Ollama Qwen with prompt"""
        if not self.ollama_available:
            raise RuntimeError("Ollama not available")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Lower temp for consistent code generation
                            "num_predict": 4096,
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "").strip()
                else:
                    raise RuntimeError(f"Ollama API error: {response.status_code}")

        except Exception as e:
            raise RuntimeError(f"Failed to call Ollama: {e}")

    def analyze_module(self, file_path: Path) -> Dict:
        """Analyze Python module and extract structure"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))

            classes = []
            functions = []
            methods = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    # Get methods
                    methods[node.name] = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods[node.name].append(item.name)
                elif isinstance(node, ast.FunctionDef):
                    # Check if it's a top-level function
                    if not any(
                        isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)
                    ):
                        functions.append(node.name)

            return {
                "file": str(file_path.relative_to(BACKEND_DIR)),
                "classes": classes,
                "functions": functions,
                "methods": methods,
                "lines": len(content.splitlines()),
            }
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return {}

    def check_existing_tests(self, module_path: str) -> List[str]:
        """Check what tests already exist for a module"""
        existing = []
        test_file = TESTS_DIR / module_path.replace(".py", "_test.py")
        if test_file.exists():
            existing.append(str(test_file))
        return existing

    def generate_test_with_qwen(self, module_info: Dict) -> str:
        """Use Qwen to generate comprehensive test"""
        module_name = Path(module_info["file"]).stem

        prompt = f"""Generate comprehensive pytest unit tests for this Python module:

File: {module_info["file"]}
Classes: {", ".join(module_info.get("classes", []))}
Functions: {", ".join(module_info.get("functions", []))}
Methods: {json.dumps(module_info.get("methods", {}), indent=2)}

Requirements:
1. 100% code coverage target
2. Test all classes, methods, and functions
3. Include edge cases and error handling
4. Use pytest fixtures where appropriate
5. Mock external dependencies
6. Follow pytest best practices
7. Include docstrings for each test

Generate complete test file with imports and all test cases."""

        system_prompt = """You are an expert Python test engineer specializing in pytest.
Generate high-quality, comprehensive unit tests that achieve maximum code coverage.
Focus on:
- Testing all code paths
- Edge cases and error conditions
- Proper mocking of external dependencies
- Clear, descriptive test names
- Good test organization"""

        try:
            test_code = self._call_qwen(prompt, system_prompt)
            return test_code
        except Exception as e:
            print(f"Error generating test with Qwen: {e}")
            return None

    def analyze_coverage_gaps(self) -> List[Dict]:
        """Analyze codebase and find coverage gaps"""
        print("🔍 Analyzing codebase for coverage gaps...")

        # Find all Python modules
        modules = []
        for file_path in BACKEND_DIR.rglob("*.py"):
            if "__pycache__" in str(file_path) or file_path.name == "__init__.py":
                continue
            if "tests" in str(file_path):
                continue

            module_info = self.analyze_module(file_path)
            if module_info:
                # Check if test exists
                existing_tests = self.check_existing_tests(module_info["file"])
                module_info["has_tests"] = len(existing_tests) > 0
                modules.append(module_info)

        # Find modules without tests
        missing_tests = [m for m in modules if not m.get("has_tests")]
        return missing_tests

    def generate_missing_tests(self, limit: int = 10):
        """Generate tests for modules missing coverage"""
        if not self.ollama_available:
            print("❌ Ollama not available. Cannot generate tests.")
            return

        gaps = self.analyze_coverage_gaps()
        print(f"\n📊 Found {len(gaps)} modules without tests")

        for i, module_info in enumerate(gaps[:limit]):
            print(
                f"\n[{i + 1}/{min(len(gaps), limit)}] Generating test for {module_info['file']}..."
            )

            test_code = self.generate_test_with_qwen(module_info)
            if test_code:
                # Determine test file path
                rel_path = Path(module_info["file"])
                test_rel_path = Path("unit") / rel_path.parent / f"test_{rel_path.name}"
                test_file_path = TESTS_DIR / test_rel_path

                # Create directory if needed
                test_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write test file
                if not test_file_path.exists():
                    with open(test_file_path, "w", encoding="utf-8") as f:
                        f.write(test_code)
                    print(f"  ✅ Created: {test_file_path.relative_to(PROJECT_ROOT)}")
                else:
                    print(f"  ⚠️  Exists: {test_file_path.relative_to(PROJECT_ROOT)}")


def main():
    """Main entry point"""
    generator = IntelligentCoverageGenerator()

    if not generator.ollama_available:
        print("\n❌ Ollama Qwen not available!")
        print("   Please ensure Ollama is running with qwen2.5:latest model")
        print("   Run: ollama pull qwen2.5:latest")
        sys.exit(1)

    print("\n🤖 Starting intelligent coverage test generation...")
    generator.generate_missing_tests(limit=10)

    print("\n✅ Coverage test generation completed!")
    print("   Run tests with: pytest apps/backend-rag/backend/tests/")


if __name__ == "__main__":
    main()
