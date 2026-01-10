"""
🛡️ AUTONOMOUS TEST GUARDIAN (v2026.2) - Enhanced with Metrics & Logging
Part of Nuzantara Intelligent Business OS.

This agent operates as a specialized QA Engineer that:
1. Analyzes Codebase Coverage autonomously
2. Identifies critical gaps (files < 99% coverage)
3. Reads Context (imports & dependencies) to understand logic
4. Generates Robust Tests using LLM (Cloud or Local)
5. Self-Heals (runs -> fails -> fixes -> runs -> passes)
6. Commits changes to a dedicated branch
7. Tracks comprehensive metrics and performance
8. Provides detailed logging and alerts

Usage:
    python -m backend.agents.agents.test_guardian --mode=auto --provider=local
"""

import ast
import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Import Test Force services
try:
    from backend.agents.services.llm_adapter import LLMAdapter, LLMProvider, LLMRequest, get_llm_adapter
    from backend.agents.services.test_metrics import get_metrics_collector
    TEST_FORCE_AVAILABLE = True
except ImportError:
    # Fallback for standalone execution
    LLMAdapter = None
    LLMProvider = None
    get_llm_adapter = None
    get_metrics_collector = None
    TEST_FORCE_AVAILABLE = False

# Import Nuzantara AI Client (fallback)
try:
    from backend.llm.zantara_ai_client import ZantaraAIClient
    ZANTARA_AVAILABLE = True
except ImportError:
    try:
        from backend.app.llm.zantara_ai_client import ZantaraAIClient
        ZANTARA_AVAILABLE = True
    except ImportError:
        ZantaraAIClient = None
        ZANTARA_AVAILABLE = False

# Enhanced Logger Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] 🛡️ TestGuardian: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
COVERAGE_THRESHOLD = 99.0
MAX_RETRIES = 3
GENERATED_TESTS_DIR = Path("backend/tests/generated")
PROJECT_ROOT = Path("apps/backend-rag/backend")  # Adjust based on execution context

# Performance thresholds
GENERATION_TIMEOUT = 120.0  # seconds
COVERAGE_TARGET = 99.0


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
    """
    Enhanced Test Guardian with comprehensive metrics and logging.
    
    Features:
    - LLM adapter integration (Ollama Qwen 2.5, Gemini, Mock)
    - Real-time metrics collection
    - Performance tracking and alerting
    - Detailed operation logging
    - Self-healing with retry logic
    """
    
    def __init__(self, provider: str = "local", local_model: str = "qwen2.5-coder:7b-instruct-q4_K_M"):
        self.provider = provider
        self.local_model = local_model
        
        # Initialize LLM Adapter (new system)
        if TEST_FORCE_AVAILABLE:
            self.llm_adapter = get_llm_adapter()
            self.metrics_collector = get_metrics_collector()
            self.agent_metrics = self.metrics_collector.register_agent("TestGuardian")
            logger.info(f"🚀 TestGuardian initialized with Test Force services")
        else:
            # Fallback to legacy system
            self.llm_adapter = None
            self.metrics_collector = None
            self.agent_metrics = None
            
            if ZANTARA_AVAILABLE:
                self.ai_client = ZantaraAIClient()
                if provider == "local":
                    logger.info(f"🌙 Night Mode: Using Local LLM ({local_model})")
                    self.ai_client.mock_mode = True
            else:
                self.ai_client = None
                logger.warning("⚠️ Running in MOCK/Dry-Run mode")

        # Ensure generated tests dir exists
        GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)
        init_file = GENERATED_TESTS_DIR / "__init__.py"
        if not init_file.exists():
            init_file.touch()

        logger.info(f"🛡️ TestGuardian ready with provider: {provider}")

    async def _generate_text(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.2) -> str:
        """
        Generate text using LLM with metrics tracking.
        
        Args:
            prompt: Input prompt for LLM
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature
            
        Returns:
            Generated text
        """
        start_time = time.time()
        
        try:
            if self.llm_adapter:
                # Use new LLM adapter system
                provider_map = {
                    "local": LLMProvider.OLLAMA,
                    "gemini": LLMProvider.GEMINI,
                    "mock": LLMProvider.MOCK
                }
                
                request = LLMRequest(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    provider=provider_map.get(self.provider, LLMProvider.OLLAMA)
                )
                
                response = await self.llm_adapter.generate(request)
                
                # Record metrics
                if self.agent_metrics:
                    self.agent_metrics.record_operation(
                        duration=response.response_time,
                        success=True
                    )
                    self.metrics_collector.record_test_generation(
                        duration=response.response_time,
                        success=True
                    )
                
                logger.info(f"✅ LLM generation: {len(response.text)} chars, {response.response_time:.2f}s")
                return response.text
                
            else:
                # Fallback to legacy system
                return await self._legacy_generate_text(prompt, max_tokens, temperature)
                
        except Exception as e:
            # Record failure
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    duration=time.time() - start_time,
                    success=False,
                    error=str(e)
                )
                self.metrics_collector.record_test_generation(
                    duration=time.time() - start_time,
                    success=False
                )
            
            logger.error(f"❌ LLM generation failed: {e}")
            return "# Mock Generated Test Code - Generation Failed"

    async def _legacy_generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Legacy generation method for fallback compatibility"""
        if self.provider == "local":
            return await self._call_local_ollama(prompt)
        elif self.ai_client:
            response = await self.ai_client.chat_async(
                messages=[{"role": "user", "content": prompt}], 
                max_tokens=max_tokens, 
                temperature=temperature
            )
            return response["text"]
        else:
            return "# Mock Generated Test Code"

    async def _call_local_ollama(self, prompt: str) -> str:
        """Direct call to Ollama for local generation (legacy fallback)"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=GENERATION_TIMEOUT) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"model": self.local_model, "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    return resp.json()["response"]
                else:
                    logger.error(f"Ollama Error: {resp.text}")
                    return ""
        except Exception as e:
            logger.error(f"Failed to call Ollama: {e}")
            return ""

    def analyze_coverage(self) -> list[dict[str, Any]]:
        """
        Runs pytest coverage and returns files needing attention.
        Enhanced with comprehensive metrics and logging.
        """
        start_time = time.time()
        logger.info("🕵️ Scanning codebase coverage...")

        # Run pytest coverage
        cmd = ["pytest", "--cov=app", "--cov-report=json:coverage.json", "-q"]

        try:
            # Record operation start
            if self.agent_metrics:
                self.agent_metrics.record_operation(0, success=False)  # Placeholder, will update
            
            logger.info(f"🔄 Running coverage command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT.parent,  # Run from app root
                check=False,
                capture_output=True,
                text=True,
                timeout=300.0  # 5 minute timeout
            )

            # Log command output
            if result.stdout:
                logger.debug(f"Coverage stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"Coverage stderr: {result.stderr}")

            report_path = PROJECT_ROOT.parent / "coverage.json"
            if not report_path.exists():
                logger.error("❌ Coverage report not found!")
                if self.agent_metrics:
                    self.agent_metrics.record_operation(
                        time.time() - start_time, 
                        success=False, 
                        error="Coverage report not found"
                    )
                return []

            # Parse coverage report
            with open(report_path) as f:
                report = json.load(f)

            # Analyze gaps
            gaps = []
            total_files = 0
            files_below_threshold = 0
            
            for file_path, data in report.get("files", {}).items():
                total_files += 1
                pct = data["summary"]["percent_covered"]
                
                if pct < COVERAGE_THRESHOLD:
                    files_below_threshold += 1
                    gaps.append({
                        "file": file_path, 
                        "percent": pct, 
                        "missing_lines": data["missing_lines"],
                        "missing_lines_count": len(data["missing_lines"]),
                        "priority": "high" if pct < 80 else "medium" if pct < 95 else "low"
                    })

            # Sort by lowest coverage first, then by missing lines count
            gaps.sort(key=lambda x: (x["percent"], x["missing_lines_count"]))

            # Calculate overall coverage
            overall_coverage = report.get("totals", {}).get("percent_covered", 0.0)
            
            # Record metrics
            duration = time.time() - start_time
            if self.agent_metrics:
                self.agent_metrics.record_operation(duration, success=True)
            
            if self.metrics_collector:
                coverage_data = {
                    "coverage": overall_coverage,
                    "files_analyzed": total_files,
                    "gaps": gaps,
                    "target": COVERAGE_THRESHOLD
                }
                self.metrics_collector.record_coverage_update(coverage_data)

            # Log comprehensive results
            logger.info(f"📊 Coverage analysis completed in {duration:.2f}s:")
            logger.info(f"   Overall coverage: {overall_coverage:.1f}% (target: {COVERAGE_THRESHOLD}%)")
            logger.info(f"   Files analyzed: {total_files}")
            logger.info(f"   Files below threshold: {files_below_threshold}")
            logger.info(f"   Coverage gaps identified: {len(gaps)}")
            
            if gaps:
                logger.info("🎯 Top 5 coverage gaps:")
                for i, gap in enumerate(gaps[:5], 1):
                    logger.info(f"   {i}. {gap['file']} - {gap['percent']:.1f}% ({gap['missing_lines_count']} missing lines)")
            
            # Check alerts
            if self.metrics_collector:
                alerts = self.metrics_collector.check_alerts()
                coverage_alerts = [a for a in alerts if a["category"] == "coverage"]
                if coverage_alerts:
                    for alert in coverage_alerts:
                        logger.warning(f"🚨 Coverage Alert: {alert['message']}")

            return gaps

        except subprocess.TimeoutExpired:
            error_msg = "Coverage analysis timed out after 5 minutes"
            logger.error(f"❌ {error_msg}")
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    time.time() - start_time, 
                    success=False, 
                    error=error_msg
                )
            return []
            
        except Exception as e:
            error_msg = f"Error analyzing coverage: {e}"
            logger.error(f"❌ {error_msg}")
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    time.time() - start_time, 
                    success=False, 
                    error=error_msg
                )
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
        except SyntaxError as e:
            logger.warning(f"Failed to parse {file_path_str}: {e}")
            return "Context extraction failed (syntax error)", code
        except Exception as e:
            logger.warning(f"Context extraction failed for {file_path_str}: {e}")
            return f"Context extraction failed: {type(e).__name__}", code

    async def generate_test(self, gap: dict[str, Any]) -> str:
        """Generates a robust test using the LLM."""

        context_summary, source_code = self.get_file_context(gap["file"])

        prompt = f"""You are an Expert QA Engineer (Python/Pytest).
TASK: Write a robust unit test to cover the missing lines in this file.

TARGET FILE: {gap["file"]}
CURRENT COVERAGE: {gap["percent"]}%
MISSING LINES: {gap["missing_lines"]}

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
            logger.info(f"🧪 Verifying {test_filename} (Attempt {attempt + 1})")

            # 1. Save
            test_path.write_text(test_code)

            # 2. Run
            result = subprocess.run(
                ["pytest", str(test_path)], cwd=PROJECT_ROOT.parent, capture_output=True, text=True
            )

            # 3. Check
            if result.returncode == 0:
                logger.info(f"✅ PASSED! Test for {target_file} secured.")
                return True

            # 4. Heal
            logger.warning("❌ FAILED. Healing...")
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
                success = await self.verify_and_heal(test_code, gap["file"])
                if success:
                    logger.info(f"🎉 Coverage Boosted for {gap['file']}")
            except Exception as e:
                logger.error(f"🔥 Critical Failure on {gap['file']}: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TestGuardian Agent")
    parser.add_argument(
        "--provider", default="gemini", choices=["gemini", "local"], help="LLM Provider"
    )
    args = parser.parse_args()

    agent = TestGuardian(provider=args.provider)
    asyncio.run(agent.run_mission())
