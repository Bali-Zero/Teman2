"""
🤖 Multi-AI Orchestrator - Uses best AI for each coding task

Integrates Qwen, Gemini, Claude, and Cursor for comprehensive coding assistance.
Routes tasks to the best AI based on task type.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

logger = logging.getLogger(__name__)


class MultiAIOrchestrator:
    """
    Orchestrator that uses multiple AI tools for coding tasks.

    Routes tasks to:
    - Qwen: Test generation, simple tasks
    - Gemini: Code analysis, documentation
    - Claude: Architecture, complex reasoning
    - Cursor: Code editing
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.multi_ai = get_multi_ai_adapter()

        # Check available tools
        available = self.multi_ai.get_available_tools()
        logger.info(f"🤖 Available AI tools: {[t.value for t in available]}")

    async def generate_test(self, file_path: str, code_context: str) -> str:
        """Generate test using Qwen (best for test generation)"""
        prompt = f"""Generate comprehensive pytest test for this Python file:

File: {file_path}
Code:
{code_context}

Requirements:
- Use pytest
- Mock all external dependencies
- Achieve 99%+ coverage
- Return ONLY Python code, no markdown"""

        request = AIRequest(
            task_type=TaskType.TEST_GENERATION,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return response.text

    async def analyze_code(self, file_path: str, code: str) -> dict[str, Any]:
        """Analyze code using Gemini (best for code analysis)"""
        prompt = f"""Analyze this Python code and provide:

1. Code quality assessment
2. Potential bugs or issues
3. Performance improvements
4. Best practice suggestions
5. Security concerns

File: {file_path}
Code:
{code}"""

        request = AIRequest(
            task_type=TaskType.CODE_ANALYSIS,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return {
            "analysis": response.text,
            "tool_used": response.tool_used.value,
        }

    async def design_architecture(self, component_name: str, requirements: str) -> dict[str, Any]:
        """Design architecture using Claude (best for complex reasoning)"""
        prompt = f"""Design architecture for: {component_name}

Requirements:
{requirements}

Provide:
1. Architecture overview
2. Component design
3. Data flow
4. API design
5. Technology choices
6. Implementation plan"""

        request = AIRequest(
            task_type=TaskType.ARCHITECTURE,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return {
            "architecture": response.text,
            "tool_used": response.tool_used.value,
        }

    async def refactor_code(self, file_path: str, code: str, goal: str) -> str:
        """Refactor code using Gemini (best for refactoring)"""
        prompt = f"""Refactor this code to: {goal}

File: {file_path}
Current code:
{code}

Provide refactored code with:
- Improved structure
- Better naming
- Performance optimizations
- Best practices
- Return ONLY code, no explanations"""

        request = AIRequest(
            task_type=TaskType.REFACTORING,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return response.text

    async def generate_documentation(self, file_path: str, code: str) -> str:
        """Generate documentation using Gemini (best for documentation)"""
        prompt = f"""Generate comprehensive documentation for this code:

File: {file_path}
Code:
{code}

Include:
- Module/class docstrings
- Function docstrings with parameters
- Usage examples
- Notes and warnings"""

        request = AIRequest(
            task_type=TaskType.DOCUMENTATION,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return response.text

    async def review_code(self, file_path: str, code: str) -> dict[str, Any]:
        """Review code using Gemini (best for code review)"""
        prompt = f"""Perform code review for:

File: {file_path}
Code:
{code}

Check for:
1. Bugs and errors
2. Code quality issues
3. Performance problems
4. Security vulnerabilities
5. Best practice violations
6. Suggestions for improvement"""

        request = AIRequest(
            task_type=TaskType.CODE_REVIEW,
            prompt=prompt,
        )

        response = await self.multi_ai.generate(request)
        return {
            "review": response.text,
            "tool_used": response.tool_used.value,
        }


# CLI interface
async def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-AI Orchestrator")
    parser.add_argument(
        "--task",
        required=True,
        choices=["test", "analyze", "architecture", "refactor", "docs", "review"],
    )
    parser.add_argument("--file", help="File path")
    parser.add_argument("--code", help="Code content")
    parser.add_argument("--project-root", default=".", help="Project root")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🤖 MultiAI: %(message)s",
    )

    orchestrator = MultiAIOrchestrator(Path(args.project_root))

    try:
        if args.task == "test":
            if not args.file or not args.code:
                logger.info("❌ --file and --code required for test generation")
                return
            result = await orchestrator.generate_test(args.file, args.code)
            logger.info(result)

        elif args.task == "analyze":
            if not args.file or not args.code:
                logger.info("❌ --file and --code required for analysis")
                return
            result = await orchestrator.analyze_code(args.file, args.code)
            logger.info(result["analysis"])

        elif args.task == "architecture":
            if not args.code:
                logger.info("❌ --code (requirements) required")
                return
            result = await orchestrator.design_architecture("Component", args.code)
            logger.info(result["architecture"])

        elif args.task == "refactor":
            if not args.file or not args.code:
                logger.info("❌ --file and --code required")
                return
            result = await orchestrator.refactor_code(args.file, args.code, "improve quality")
            logger.info(result)

        elif args.task == "docs":
            if not args.file or not args.code:
                logger.info("❌ --file and --code required")
                return
            result = await orchestrator.generate_documentation(args.file, args.code)
            logger.info(result)

        elif args.task == "review":
            if not args.file or not args.code:
                logger.info("❌ --file and --code required")
                return
            result = await orchestrator.review_code(args.file, args.code)
            logger.info(result["review"])

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
