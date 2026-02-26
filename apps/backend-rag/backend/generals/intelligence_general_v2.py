"""
Intelligence General v2 - Hybrid Research with Web Search

Combines internal data (Knowledge Graph, Vector DB) with live web search (Brave API)
for comprehensive research and fact-checking. Replaces separate Perplexity General.

Polls generals_tasks table for tasks with task_type='research',
executes multi-step research workflow, and updates status/result in the database.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings
from backend.generals.onboarding_context import (
    get_intelligence_system_instruction_v2,
    log_onboarding_compliance,
)

# Import Gemini client
try:
    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient, get_genai_client
except ImportError:
    GENAI_AVAILABLE = False
    GenAIClient = None
    get_genai_client = None

logger = logging.getLogger(__name__)


class IntelligenceGeneralV2:
    """
    Intelligence General v2 - Hybrid Strategist.

    Capabilities:
    - Internal data: Knowledge Graph (PostgreSQL), Vector DB (Qdrant)
    - External data: Web search via Brave Search API
    - Multi-step research workflow
    - Fact-checking with source verification
    - Inter-agent coordination via shared memory

    Every research task includes AI_ONBOARDING.md context via system prompt.
    """

    def __init__(self, database_url: str | None = None, poll_interval: int = 5):
        """
        Initialize Intelligence General v2.

        Args:
            database_url: PostgreSQL connection string (defaults to settings.database_url)
            poll_interval: Seconds between task polls (default: 5)
        """
        self.database_url = database_url or settings.database_url
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        self.poll_interval = poll_interval
        self.pool: asyncpg.Pool | None = None
        self.running = False
        self.general_name = "intelligence_general"

        # Load onboarding context - our constitution
        log_onboarding_compliance(self.general_name)

        # Initialize Gemini client
        self.genai_client: GenAIClient | None = None
        if GENAI_AVAILABLE and get_genai_client:
            try:
                self.genai_client = get_genai_client()
                if not self.genai_client.is_available:
                    logger.warning("⚠️ Intelligence General v2: Gemini client not available")
                    self.genai_client = None
                else:
                    logger.info("✅ Intelligence General v2: Gemini client initialized")
            except Exception as e:
                logger.error(
                    f"❌ Intelligence General v2: Failed to initialize Gemini: {e}", exc_info=True
                )
                self.genai_client = None
        else:
            logger.warning("⚠️ Intelligence General v2: Gemini SDK not available")

        # Brave Search API key
        self.brave_api_key = settings.brave_api_key
        if not self.brave_api_key:
            logger.warning(
                "⚠️ Intelligence General v2: Brave API key not configured (web search disabled)"
            )

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ Intelligence General v2: Database pool initialized")
        except Exception as e:
            logger.error(
                f"❌ Intelligence General v2: Failed to initialize pool: {e}", exc_info=True
            )
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("✅ Intelligence General v2: Database pool closed")

    async def _log_activity(
        self,
        activity_type: str,
        message: str,
        task_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log activity to generals_activity table."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_activity (general_name, task_id, activity_type, message, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    self.general_name,
                    task_id,
                    activity_type,
                    message,
                    json.dumps(metadata or {}),
                )
        except Exception as e:
            logger.warning(f"Failed to log activity: {e}")

    async def _read_memory(self, key: str) -> dict[str, Any] | None:
        """
        Read from shared memory.

        Args:
            key: Memory key

        Returns:
            Memory value or None if not found/expired
        """
        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT value, expires_at
                    FROM generals_memory
                    WHERE key = $1
                    """,
                    key,
                )

                if not row:
                    return None

                # Check expiration
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    # Expired, delete it
                    await conn.execute(
                        """
                        DELETE FROM generals_memory
                        WHERE key = $1
                        """,
                        key,
                    )
                    return None

                await self._log_activity(
                    "memory_read", f"Read memory key: {key}", metadata={"key": key}
                )
                return dict(row["value"])

        except Exception as e:
            logger.error(f"❌ Intelligence General v2: Error reading memory: {e}", exc_info=True)
            return None

    async def _write_memory(
        self, key: str, value: dict[str, Any], expires_at: datetime | None = None
    ) -> None:
        """
        Write to shared memory.

        Args:
            key: Memory key
            value: Memory value (will be stored as JSONB)
            expires_at: Optional expiration timestamp
        """
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO generals_memory (key, value, general_name, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (key) DO UPDATE
                    SET value = $2,
                        general_name = $3,
                        expires_at = $4,
                        updated_at = NOW()
                    """,
                    key,
                    json.dumps(value),
                    self.general_name,
                    expires_at,
                )

                await self._log_activity(
                    "memory_written",
                    f"Wrote memory key: {key}",
                    metadata={"key": key, "expires_at": str(expires_at)},
                )

        except Exception as e:
            logger.error(f"❌ Intelligence General v2: Error writing memory: {e}", exc_info=True)

    async def _web_search(
        self, query: str, num_results: int = 5, freshness: str | None = None
    ) -> dict[str, Any]:
        """
        Execute web search using Brave Search API.

        Args:
            query: Search query
            num_results: Number of results to return (default: 5, max: 10)
            freshness: Time filter - 'pd' (past day), 'pw' (past week), 'pm' (past month), 'py' (past year)

        Returns:
            {
                "success": bool,
                "results": [{"title": str, "url": str, "snippet": str, "age": str}],
                "query": str,
                "error": str | None
            }
        """
        if not self.brave_api_key:
            return {
                "success": False,
                "results": [],
                "query": query,
                "error": "Brave API key not configured",
            }

        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.brave_api_key,
            }
            params = {
                "q": query,
                "count": min(num_results, 10),  # Brave max is 10
                "text_decorations": False,
                "search_lang": "en",
            }

            if freshness:
                params["freshness"] = freshness

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                # Extract web results
                results = []
                for item in data.get("web", {}).get("results", []):
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("description", ""),
                            "age": item.get("age", ""),
                        }
                    )

                return {"success": True, "results": results, "query": query, "error": None}

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"❌ Intelligence General v2: Web search failed: {error_msg}", exc_info=True
            )
            return {"success": False, "results": [], "query": query, "error": error_msg}

    async def poll_task(self) -> dict[str, Any] | None:
        """
        Poll for pending research tasks.

        Returns:
            Task record or None if no tasks available
        """
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as conn:
                # Get highest priority pending task
                task = await conn.fetchrow(
                    """
                    SELECT id, task_type, title, description, payload, priority, created_at
                    FROM generals_tasks
                    WHERE task_type = 'research'
                      AND status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )

                if not task:
                    return None

                # Assign task to this general
                await conn.execute(
                    """
                    UPDATE generals_tasks
                    SET status = 'assigned',
                        assigned_to = $1,
                        assigned_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    self.general_name,
                    task["id"],
                )

                await self._log_activity(
                    "task_polled",
                    f"Polled task: {task['title']}",
                    task_id=task["id"],
                )

                return dict(task)

        except Exception as e:
            logger.error(f"❌ Intelligence General v2: Error polling task: {e}", exc_info=True)
            await self._log_activity("error", f"Poll error: {str(e)}", metadata={"error": str(e)})
            return None

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a research task using multi-step workflow.

        Workflow:
        1. Internal scan (check shared memory for recent research)
        2. Web search (if needed) for current information
        3. Synthesis using Gemini with both internal + external data
        4. Save key findings to shared memory

        Args:
            task: Task record from database

        Returns:
            Result dictionary with status, analysis, sources, etc.
        """
        task_id = task["id"]
        title = task["title"]
        description = task.get("description", "")
        payload = task.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)

        logger.info(f"🧠 Intelligence General v2: Executing task {task_id}: {title}")

        await self._log_activity(
            "task_started",
            f"Started hybrid research: {title}",
            task_id=task_id,
            metadata={"payload": payload},
        )

        # Update status to in_progress
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE generals_tasks
                        SET status = 'in_progress',
                            started_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        task_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to update task status: {e}")

        result = {
            "status": "failed",
            "analysis": "",
            "insights": [],
            "sources": [],
            "web_search_results": [],
            "internal_sources": [],
            "error": None,
            "model_used": None,
            "token_usage": {},
            "execution_time_seconds": 0,
            "confidence_level": "low",
        }

        start_time = datetime.now(timezone.utc)

        try:
            if not self.genai_client:
                raise RuntimeError("Gemini client not available")

            # Extract research parameters from payload
            query = payload.get("query") or description or title
            context = payload.get("context", "")
            memory_keys = payload.get("memory_keys", [])
            save_to_memory = payload.get("save_to_memory", False)
            memory_key = payload.get("memory_key")
            memory_ttl_seconds = payload.get("memory_ttl_seconds", 86400)  # 24h default
            use_web_search = payload.get("use_web_search", True)  # Enable by default
            web_search_freshness = payload.get("web_search_freshness")  # 'pd', 'pw', 'pm', 'py'
            num_web_results = payload.get("num_web_results", 5)
            depth = payload.get("depth", "standard")  # "quick", "standard", "deep"
            max_tokens = payload.get("max_tokens", 8192)
            temperature = payload.get("temperature", 0.7)

            # Step 1: Internal scan - check shared memory
            memory_context = ""
            internal_sources = []
            if memory_keys:
                memory_data = []
                for key in memory_keys:
                    mem_value = await self._read_memory(key)
                    if mem_value:
                        memory_data.append(f"{key}: {json.dumps(mem_value)}")
                        internal_sources.append(f"Memory:{key}")
                if memory_data:
                    memory_context = "\n\n### Internal Memory Context:\n" + "\n".join(memory_data)

            # Step 2: Web search (if enabled and API key available)
            web_search_context = ""
            web_search_results = []
            if use_web_search and self.brave_api_key:
                logger.info(f"🔍 Intelligence General v2: Executing web search for '{query}'")
                search_result = await self._web_search(
                    query, num_results=num_web_results, freshness=web_search_freshness
                )

                if search_result["success"]:
                    web_search_results = search_result["results"]
                    if web_search_results:
                        web_context_lines = []
                        for i, item in enumerate(web_search_results, 1):
                            web_context_lines.append(
                                f"{i}. **{item['title']}**\n   URL: {item['url']}\n   {item['snippet']}\n   Age: {item.get('age', 'unknown')}"
                            )
                        web_search_context = "\n\n### Live Web Search Results:\n" + "\n\n".join(
                            web_context_lines
                        )
                else:
                    logger.warning(f"⚠️ Web search failed: {search_result['error']}")
                    web_search_context = (
                        f"\n\n### Web Search Status:\nFailed: {search_result['error']}"
                    )

            # Step 3: Build system instruction (v2 hybrid prompt)
            system_instruction = get_intelligence_system_instruction_v2()

            # Step 4: Build user prompt with all context
            user_prompt = f"""# Research Query: {query}"""
            if description and description != query:
                user_prompt += f"\n\n## Task Description:\n{description}"
            if context:
                user_prompt += f"\n\n## Additional Context:\n{context}"
            if memory_context:
                user_prompt += memory_context
            if web_search_context:
                user_prompt += web_search_context

            user_prompt += f"\n\n## Research Depth: {depth.upper()}"
            user_prompt += "\n\nPlease provide a comprehensive analysis following the Intelligence General v2 format (Executive Summary, Key Findings, Detailed Analysis, Strategic Recommendations, Sources, Confidence Level)."

            # Step 5: Use Gemini for synthesis
            model_name = payload.get("model") or "gemini-2.0-flash-001"

            logger.info(f"🧠 Intelligence General v2: Using model {model_name} for synthesis")

            response = await self.genai_client.generate_content(
                contents=user_prompt,
                model=model_name,
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            analysis_text = response.get("text", "")
            model_used = response.get("model", model_name)
            token_usage = response.get("usage", {})

            # Step 6: Extract structured insights (enhanced)
            insights = []
            confidence_level = "medium"  # Default

            # Extract confidence level from analysis
            if "confidence level:" in analysis_text.lower():
                if "high" in analysis_text.lower():
                    confidence_level = "high"
                elif "low" in analysis_text.lower():
                    confidence_level = "low"

            # Extract insights from "Key Findings" or similar sections
            lines = analysis_text.split("\n")
            in_findings_section = False
            for line in lines:
                lower_line = line.lower()
                if "key finding" in lower_line or "## key finding" in lower_line:
                    in_findings_section = True
                    continue
                if in_findings_section and line.strip().startswith("-"):
                    insights.append(line.strip())
                if (
                    in_findings_section
                    and line.strip().startswith("##")
                    and "key finding" not in lower_line
                ):
                    in_findings_section = False

            # Extract sources from web search + analysis
            sources = []
            for web_result in web_search_results:
                sources.append(f"{web_result['title']} - {web_result['url']}")

            # Also extract sources mentioned in analysis
            for line in lines:
                if any(
                    keyword in line.lower() for keyword in ["source:", "reference:", "http", "www."]
                ):
                    sources.append(line.strip())

            result["status"] = "completed"
            result["analysis"] = analysis_text
            result["insights"] = insights[:15]  # Limit to 15
            result["sources"] = list(set(sources))[:20]  # Dedupe, limit to 20
            result["web_search_results"] = web_search_results
            result["internal_sources"] = internal_sources
            result["model_used"] = model_used
            result["token_usage"] = token_usage
            result["confidence_level"] = confidence_level

            # Step 7: Save to memory if requested
            if save_to_memory and memory_key:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=memory_ttl_seconds)

                await self._write_memory(
                    memory_key,
                    {
                        "task_id": task_id,
                        "query": query,
                        "analysis": analysis_text[:2000],  # Truncate for memory storage
                        "insights": insights,
                        "sources": sources[:10],
                        "confidence_level": confidence_level,
                        "model_used": model_used,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    expires_at=expires_at,
                )

        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            logger.error(
                f"❌ Intelligence General v2: Task {task_id} failed: {error_msg}", exc_info=True
            )

        finally:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            result["execution_time_seconds"] = execution_time

        # Update task in database
        await self._update_task_result(task_id, result)

        return result

    async def _update_task_result(self, task_id: int, result: dict[str, Any]) -> None:
        """Update task with execution result."""
        if not self.pool:
            return

        try:
            status = "completed" if result["status"] == "completed" else "failed"
            error_message = result.get("error")

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE generals_tasks
                    SET status = $1,
                        result = $2,
                        error_message = $3,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $4
                    """,
                    status,
                    json.dumps(result),
                    error_message,
                    task_id,
                )

            await self._log_activity(
                f"task_{status}",
                f"Task {status}: {result.get('confidence_level', 'unknown')} confidence",
                task_id=task_id,
                metadata={
                    "execution_time": result.get("execution_time_seconds"),
                    "model_used": result.get("model_used"),
                    "token_usage": result.get("token_usage"),
                    "confidence_level": result.get("confidence_level"),
                    "web_search_used": len(result.get("web_search_results", [])) > 0,
                    "sources_count": len(result.get("sources", [])),
                },
            )

        except Exception as e:
            logger.error(
                f"❌ Intelligence General v2: Failed to update task result: {e}", exc_info=True
            )

    async def run_loop(self) -> None:
        """Main polling loop - runs indefinitely."""
        if not self.pool:
            await self.initialize()

        if not self.genai_client:
            logger.error("❌ Intelligence General v2: Cannot start - Gemini client not available")
            return

        self.running = True
        logger.info("🚀 Intelligence General v2: Starting hybrid research polling loop")

        while self.running:
            try:
                task = await self.poll_task()

                if task:
                    await self.execute_task(task)
                else:
                    # No tasks available, wait before next poll
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("🛑 Intelligence General v2: Polling loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"❌ Intelligence General v2: Error in polling loop: {e}", exc_info=True
                )
                await asyncio.sleep(self.poll_interval)

        logger.info("✅ Intelligence General v2: Polling loop stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        self.running = False
        logger.info("🛑 Intelligence General v2: Stop requested")
