"""
🤖 AUTONOMOUS CONVERSATION TRAINER
Learns from successful conversations and improves prompts automatically
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg

try:
    from backend.llm.zantara_ai_client import ZantaraAIClient
    ZANTARA_AVAILABLE = True
except ImportError:
    ZantaraAIClient = None
    ZANTARA_AVAILABLE = False

try:
    from backend.app.utils.secure_subprocess import safe_git_checkout_new, safe_git_checkout, safe_git_add, safe_git_commit
except ImportError:
    # Fallback if secure_subprocess not available
    import subprocess
    safe_git_checkout_new = lambda branch, cwd=None: subprocess.run(["git", "checkout", "-b", branch], cwd=cwd, check=True, capture_output=True)
    safe_git_checkout = lambda branch, cwd=None: subprocess.run(["git", "checkout", branch], cwd=cwd, check=False, capture_output=True)
    safe_git_add = lambda files, cwd=None: subprocess.run(["git", "add"] + files, cwd=cwd, check=True, timeout=10.0)
    safe_git_commit = lambda message, cwd=None: subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True, timeout=10.0)

logger = logging.getLogger(__name__)

# Constants
MIN_RATING_THRESHOLD = 4
TOP_CONVERSATIONS_LIMIT = 50
ANALYSIS_CONVERSATIONS_LIMIT = 10


class ConversationTrainer:
    """
    Autonomous agent that:
    1. Finds high-rated conversations (rating >= 4)
    2. Extracts successful patterns with AI
    3. Generates improved prompt suggestions
    4. Creates PR with prompt improvements
    """

    def __init__(
        self, db_pool: asyncpg.Pool | None = None, zantara_client: ZantaraAIClient | None = None
    ):
        """
        Initialize ConversationTrainer with dependencies.

        Args:
            db_pool: AsyncPG connection pool (if None, will try to get from backend.app.state)
            zantara_client: ZantaraAIClient instance (if None, will create new)
        """
        self.db_pool = db_pool
        self.zantara_client = zantara_client or (ZantaraAIClient() if ZANTARA_AVAILABLE else None)

    async def _get_db_pool(self) -> asyncpg.Pool:
        """Get database pool from instance or app.state"""
        if self.db_pool:
            return self.db_pool

        # Try to get from backend.app.state
        try:
            from backend.app.main_cloud import app

            pool = getattr(app.state, "db_pool", None)
            if pool:
                return pool
        except Exception:
            pass

        raise RuntimeError(
            "Database pool not available. Provide db_pool in __init__ or ensure app.state.db_pool is set."
        )

    async def analyze_winning_patterns(
        self, days_back: int = 7, timeout: float = 60.0
    ) -> dict[str, Any] | None:
        """Find patterns in successful conversations"""
        if days_back < 1 or days_back > 365:
            logger.warning(f"Invalid days_back value: {days_back}, using default 7")
            days_back = 7

        try:
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                # Query top conversations from v_rated_conversations view
                # This view aggregates conversation_ratings with conversation_history
                rows = await conn.fetch(
                    """
                    SELECT
                        conversation_id,
                        messages,
                        rating,
                        client_feedback,
                        created_at
                    FROM v_rated_conversations
                    WHERE rating >= $1
                      AND created_at >= NOW() - $2::interval
                    ORDER BY rating DESC, created_at DESC
                    LIMIT $3
                    """,
                    MIN_RATING_THRESHOLD,
                    timedelta(days=days_back),
                    TOP_CONVERSATIONS_LIMIT,
                )

                if not rows:
                    logger.info(f"No high-rated conversations found in last {days_back} days")
                    return None

                # Prepare conversation data for analysis
                top_conversations = rows[:ANALYSIS_CONVERSATIONS_LIMIT]
                conversation_texts = []

                for row in top_conversations:
                    messages_data = row["messages"]
                    # Parse messages if JSON string
                    if isinstance(messages_data, str):
                        try:
                            messages_data = json.loads(messages_data)
                        except json.JSONDecodeError:
                            messages_data = [{"content": messages_data}]

                    # Format conversation
                    conv_text = f"Rating: {row['rating']}/5\n"
                    if row["client_feedback"]:
                        conv_text += f"Feedback: {row['client_feedback']}\n"
                    conv_text += "Messages:\n"

                    if isinstance(messages_data, list):
                        for msg in messages_data:
                            role = msg.get("role", "user")
                            content = msg.get("content", "")
                            conv_text += f"{role}: {content}\n"
                    else:
                        conv_text += str(messages_data)

                    conversation_texts.append(conv_text)

                # Use AI to extract patterns
                if self.zantara_client:
                    analysis_prompt = f"""Analyze these successful conversations and extract patterns:

{chr(10).join(["---", *conversation_texts, "---"])}

Extract:
1. Successful patterns (what made these conversations good)
2. Prompt improvements (how to improve system prompt based on these patterns)
3. Common themes

Return JSON:
{{
    "successful_patterns": ["pattern1", "pattern2"],
    "prompt_improvements": ["improvement1", "improvement2"],
    "common_themes": ["theme1", "theme2"]
}}"""

                    try:
                        analysis_text = await asyncio.wait_for(
                            self.zantara_client.generate_text(
                                prompt=analysis_prompt, max_tokens=8192, temperature=0.3
                            ),
                            timeout=timeout,
                        )

                        # Extract JSON from response
                        json_start = analysis_text.find("{")
                        json_end = analysis_text.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            analysis = json.loads(analysis_text[json_start:json_end])
                            return analysis
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout analyzing patterns with AI after {timeout}s")
                    except Exception as e:
                        logger.error(f"Error analyzing patterns with AI: {e}", exc_info=True)

                # Fallback: return basic analysis
                return {
                    "successful_patterns": [
                        f"High ratings ({len(top_conversations)} conversations analyzed)",
                        "Positive client feedback",
                    ],
                    "prompt_improvements": [],
                    "common_themes": [],
                }

        except asyncpg.PostgresError as e:
            logger.error(f"Database error analyzing winning patterns: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error analyzing winning patterns: {e}", exc_info=True)
            return None

    async def generate_prompt_update(self, analysis: dict[str, Any], timeout: float = 60.0) -> str:
        """Generate improved system prompt based on analysis"""
        if not analysis:
            logger.warning("Empty analysis provided to generate_prompt_update")
            return ""

        if self.zantara_client:
            prompt = f"""Based on this conversation analysis, generate an improved system prompt:

Analysis:
{json.dumps(analysis, indent=2)}

Generate an improved system prompt that incorporates the successful patterns and improvements identified.
Return ONLY the prompt text, no explanations."""

            try:
                improved_prompt = await asyncio.wait_for(
                    self.zantara_client.generate_text(
                        prompt=prompt, max_tokens=8192, temperature=0.5
                    ),
                    timeout=timeout,
                )
                return improved_prompt.strip()
            except asyncio.TimeoutError:
                logger.error(f"Timeout generating prompt update after {timeout}s")
            except Exception as e:
                logger.error(f"Error generating prompt update: {e}", exc_info=True)

        # Fallback: return analysis summary
        patterns = analysis.get("successful_patterns", [])
        improvements = analysis.get("prompt_improvements", [])

        return f"""# Improved System Prompt

Based on analysis of successful conversations:

## Successful Patterns:
{chr(10).join(f"- {p}" for p in patterns)}

## Prompt Improvements:
{chr(10).join(f"- {i}" for i in improvements)}
"""

    async def create_improvement_pr(self, improved_prompt: str, analysis: dict[str, Any]) -> str:
        """Create improvement branch and commit changes (platform agnostic)"""
        if not improved_prompt:
            raise ValueError("Improved prompt cannot be empty")

        try:
            # Create branch name (sanitized)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M")
            branch_name = f"auto/prompt-improvement-{timestamp}"

            # Get prompt file path
            prompt_file = Path("apps/backend-rag/backend/prompts/zantara_system_prompt.md")
            prompt_file.parent.mkdir(parents=True, exist_ok=True)

            # Create reports directory
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            report_file = reports_dir / f"conversation_analysis_{timestamp}.md"
            repo_path = Path(".")

            # 1. Create branch (safe subprocess)
            try:
                safe_git_checkout_new(branch_name, cwd=repo_path)
            except Exception as e:
                logger.warning(f"Branch {branch_name} may already exist: {e}")
                # Try to checkout existing branch
                try:
                    safe_git_checkout(branch_name, cwd=repo_path)
                except Exception as checkout_error:
                    logger.error(f"Failed to checkout branch {branch_name}: {checkout_error}")
                    raise RuntimeError(f"Failed to checkout branch: {checkout_error}")

            # 2. Update prompt file
            prompt_file.write_text(improved_prompt, encoding="utf-8")

            # 3. Create analysis report
            report_content = f"""# Conversation Quality Analysis

Date: {datetime.now().isoformat()}

## Analysis Results

{json.dumps(analysis, indent=2)}

## Prompt Changes

See `{prompt_file}` for updated system prompt.

## Next Steps

1. Review changes in PR
2. Test with sample conversations
3. Deploy if approved
4. Monitor rating changes
"""
            report_file.write_text(report_content, encoding="utf-8")

            # 4. Commit (safe subprocess)
            commit_message = f"feat(prompts): auto-improve based on {datetime.now().strftime('%Y-%m-%d')} conversation analysis"

            safe_git_add([str(prompt_file), str(report_file)], cwd=repo_path)
            safe_git_commit(commit_message, cwd=repo_path)

            # 5. Branch and commit created locally
            # No remote push - deploy manually via flyctl deploy
            logger.info(f"Branch {branch_name} created and committed locally.")
            logger.info(f"✅ Improvement branch ready: {branch_name}")
            logger.info("Review changes and deploy manually via flyctl deploy if approved.")
            return branch_name

        except subprocess.TimeoutExpired as e:
            logger.error(f"Subprocess timeout creating PR: {e}", exc_info=True)
            raise RuntimeError(f"Timeout creating PR: {e}") from e
        except subprocess.CalledProcessError as e:
            logger.error(f"Subprocess error creating PR: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create PR: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating PR: {e}", exc_info=True)
            raise


# Cron job entry (add to backend-ts cron)
async def run_conversation_trainer(days_back: int = 7):
    """Weekly conversation analysis and prompt improvement"""
    try:
        # Get db_pool from backend.app.state
        from backend.app.main_cloud import app

        db_pool = getattr(app.state, "db_pool", None)

        trainer = ConversationTrainer(db_pool=db_pool)

        # 1. Analyze
        analysis = await trainer.analyze_winning_patterns(days_back=days_back)

        if not analysis:
            logger.info("No high-rated conversations found")
            return

        # 2. Generate improved prompt
        improved_prompt = await trainer.generate_prompt_update(analysis)

        # 3. Create PR
        pr_branch = await trainer.create_improvement_pr(improved_prompt, analysis)

        logger.info(f"✅ Created PR on branch: {pr_branch}")

        # 4. Notify team
        from backend.app.core.config import settings

        if settings.slack_webhook_url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        settings.slack_webhook_url,
                        json={
                            "text": f"🤖 New prompt improvement PR created: {pr_branch}\n\nAnalyzed {ANALYSIS_CONVERSATIONS_LIMIT} top conversations, found actionable improvements!"
                        },
                    )
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in ConversationTrainer: {e}", exc_info=True)
        raise
