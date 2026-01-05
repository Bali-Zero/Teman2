"""
🛡️ AUTONOMOUS TEST GUARDIAN (v2026.1)
Part of Nuzantara Intelligent Business OS.

This agent operates as a specialized QA Engineer that:
1. Analyzes Codebase Coverage autonomously
2. Identifies critical gaps (files < 99% coverage)
3. Reads Context (imports & dependencies) to understand logic
4. Generates Robust Tests using LLM (Cloud or Local)
5. Self-Heals (runs -> fails -> fixes -> runs -> passes)
6. Commits changes to a dedicated branch

Usage:
    python -m backend.agents.agents.test_guardian --mode=auto --provider=gemini
"""

import asyncio
import json
import logging
import subprocess
import ast
from pathlib import Path
from typing import Any, List, Dict, Optional
from datetime import datetime

# Import Nuzantara AI Client
try:
    from app.llm.zantara_ai_client import ZantaraAIClient
    ZANTARA_AVAILABLE = True
except ImportError:
    # Fallback for standalone execution outside app context
    try:
        from backend.llm.zantara_ai_client import ZantaraAIClient
        ZANTARA_AVAILABLE = True
    except ImportError:
        ZantaraAIClient = None
        ZANTARA_AVAILABLE = False

# Logger Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] 🛡️ TestGuardian: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Constants
COVERAGE_THRESHOLD = 99.0
MAX_RETRIES = 3
GENERATED_TESTS_DIR = Path("backend/tests/generated")
PROJECT_ROOT = Path("apps/backend-rag/backend")  # Adjust based on execution context

class CodeContextAnalyzer(ast.NodeVisitor):
    """Analyzes Python code to find imports and dependencies for better context."""
    def __init__(self):
        self.imports = []
        self.classes = []
        self.functions = []

    def visit_Import(self, node):
        for name in node.names:
            self.imports.append(name.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for name in node.names:
            self.imports.append(f"{module}.{name.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)

class TestGuardian:
    def __init__(self, provider: str = "gemini", local_model: str = "qwen2.5-coder:32b"):
        self.provider = provider
        self.local_model = local_model
        
        # Initialize AI Client
        if ZANTARA_AVAILABLE:
            self.ai_client = ZantaraAIClient()
            if provider == "local":
                logger.info(f"🌙 Night Mode: Using Local LLM ({local_model})")
                self.ai_client.mock_mode = True # We'll override the chat method for local
        else:
            logger.warning("⚠️ ZantaraAIClient not found. Running in MOCK/Dry-Run mode.")
            self.ai_client = None

        # Ensure generated tests dir exists
        GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)
        init_file = GENERATED_TESTS_DIR / "__init__.py"
        if not init_file.exists():
            init_file.touch()

    async def _generate_text(self, prompt: str) -> str:
        """Wrapper to handle Cloud vs Local generation."""
        if self.provider == "local":
            return await self._call_local_ollama(prompt)
        elif self.ai_client:
            response = await self.ai_client.chat_async(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.2
            )
            return response["text"]
        else:
            return "# Mock Generated Test Code"

    async def _call_local_ollama(self, prompt: str) -> str:
        """Direct call to Ollama for local generation."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.local_model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if resp.status_code == 200:
                    return resp.json()["response"]
                else:
                    logger.error(f"Ollama Error: {resp.text}")
                    return ""
        except Exception as e:
            logger.error(f"Failed to call Ollama: {e}")
            return ""

    def analyze_coverage(self) -> List[Dict[str, Any]]:
        """Runs pytest coverage and returns files needing attention."""
        logger.info("🕵️ Scanning codebase coverage...")
        
        # Run pytest coverage
        cmd = [
            "pytest",
            "--cov=backend",
            "--cov-report=json:coverage_report.json",
            "-q"
        ]
        
        try:
            subprocess.run(
                ["pytest", "--cov=app", "--cov-report=json:coverage.json", "-q"],
                cwd=PROJECT_ROOT.parent, # Run from app root
                check=False,
                capture_output=True
            )
            
            report_path = PROJECT_ROOT.parent / "coverage.json"
            if not report_path.exists():
                logger.error("❌ Coverage report not found!")
                return []

            with open(report_path) as f:
                report = json.load(f)

            gaps = []
            for file_path, data in report.get("files", {}).items():
                pct = data["summary"]["percent_covered"]
                if pct < COVERAGE_THRESHOLD:
                    gaps.append({
                        "file": file_path,
                        "percent": pct,
                        "missing_lines": data["missing_lines"]
                    })
            
            # Sort by lowest coverage first
            gaps.sort(key=lambda x: x["percent"])
            return gaps

        except Exception as e:
            logger.error(f"Error analyzing coverage: {e}")
            return []

    def get_file_context(self, file_path_str: str) -> str:
        """Reads file and extracts context (imports, classes)."""
        file_path = PROJECT_ROOT.parent / file_path_str
        if not file_path.exists():
            return ""
        
        code = file_path.read_text()
        
        try:
            tree = ast.parse(code)
            analyzer = CodeContextAnalyzer()
            analyzer.visit(tree)
            
            context = f"Imports used: {', '.join(analyzer.imports)}\n"
            context += f"Classes defined: {', '.join(analyzer.classes)}\n"
            context += f"Functions defined: {', '.join(analyzer.functions)}\n"
            return context, code
        except:
            return "Context extraction failed", code

    async def generate_test(self, gap: Dict[str, Any]) -> str:
        """Generates a robust test using the LLM."""
        
        context_summary, source_code = self.get_file_context(gap["file"])
        
        prompt = f"""You are an Expert QA Engineer (Python/Pytest).
TASK: Write a robust unit test to cover the missing lines in this file.

TARGET FILE: {gap['file']}
CURRENT COVERAGE: {gap['percent']}%
MISSING LINES: {gap['missing_lines']}

CONTEXT (Dependencies):
{context_summary}

SOURCE CODE:
```python
{source_code}
```

REQUIREMENTS:
1. Use `pytest` and `pytest-asyncio` (if async code).
2. Mock ALL external dependencies (DB, APIs, Redis) using `unittest.mock` or `pytest-mock`.
3. Focus ONLY on covering the logic in the MISSING LINES.
4. Add the header: `# Generated by TestGuardian on {datetime.now().date()}`
5. Return ONLY the Python code block. No markdown, no explanation.
"""
        
        raw_response = await self._generate_text(prompt)
        
        # Clean response (remove markdown code blocks)
        code = raw_response.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
            
        return code.strip()

    async def verify_and_heal(self, test_code: str, target_file: str) -> bool:
        """Self-healing loop: Write -> Run -> Fix -> Repeat."""
        
        safe_name = target_file.replace("/", "_").replace(".py", "")
        test_filename = f"test_auto_{safe_name}.py"
        test_path = GENERATED_TESTS_DIR / test_filename
        
        for attempt in range(MAX_RETRIES):
            logger.info(f"🧪 Verifying {test_filename} (Attempt {attempt+1})")
            
            # 1. Save
            test_path.write_text(test_code)
            
            # 2. Run
            result = subprocess.run(
                ["pytest", str(test_path)],
                cwd=PROJECT_ROOT.parent,
                capture_output=True,
                text=True
            )
            
            # 3. Check
            if result.returncode == 0:
                logger.info(f"✅ PASSED! Test for {target_file} secured.")
                return True
            
            # 4. Heal
            logger.warning(f"❌ FAILED. Healing...")
            error_msg = result.stderr + "\n" + result.stdout
            
            fix_prompt = f"""The generated test failed. Fix it using the Error Output.

CODE:
```python
{test_code}
```

ERROR OUTPUT:
{error_msg}

TASK: Return the FIXED Python code only.
"""
            test_code = await self._generate_text(fix_prompt)
            
            # Clean response again
            test_code = test_code.replace("```python", "").replace("```", "").strip()

        logger.error(f"💀 GIVE UP. Could not fix test for {target_file} after {MAX_RETRIES} tries.")
        # Cleanup failed test to not break build
        if test_path.exists():
            test_path.unlink()
        return False

    async def run_mission(self):
        """Main entry point."""
        logger.info("🚀 TestGuardian Mission Started")
        
        gaps = self.analyze_coverage()
        if not gaps:
            logger.info("✨ Coverage already excellent (or report missing).")
            return

        logger.info(f"📉 Identified {len(gaps)} files below {COVERAGE_THRESHOLD}% coverage.")
        
        # Limit to top 5 worst offenders per run to keep it manageable
        for gap in gaps[:5]:
            logger.info(f"🎯 Targeting: {gap['file']} ({gap['percent']}%)")
            
            try:
                test_code = await self.generate_test(gap)
                success = await self.verify_and_heal(test_code, gap['file'])
                if success:
                    logger.info(f"🎉 Coverage Boosted for {gap['file']}")
            except Exception as e:
                logger.error(f"🔥 Critical Failure on {gap['file']}: {e}")

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='TestGuardian Agent')
    parser.add_argument('--provider', default='gemini', choices=['gemini', 'local'], help='LLM Provider')
    args = parser.parse_args()

    agent = TestGuardian(provider=args.provider)
    asyncio.run(agent.run_mission())
