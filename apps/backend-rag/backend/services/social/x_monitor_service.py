"""
X/Twitter Social Listening Monitor Service.

Polls GET /2/tweets/search/recent every N minutes for keyword matches,
classifies intent, creates CRM leads, and notifies via Telegram.
Every 3 hours, posts a digest tweet from @balizerobot with relevant findings.
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Intent classification keywords
LEAD_KEYWORDS = {
    "help",
    "need",
    "looking for",
    "recommend",
    "how to",
    "want to",
    "set up",
    "setup",
    "register",
    "open",
    "start",
    "apply",
    "cost",
    "price",
    "how much",
    "berapa",
    "butuh",
    "cari",
    "anyone know",
    "any tips",
    "advice",
    "experience with",
}
SPAM_KEYWORDS = {
    "giveaway",
    "airdrop",
    "crypto",
    "nft",
    "free money",
    "dm me",
    "pump",
    "signal",
    "#crypto",
    "token",
    "whitelist",
    "presale",
}

# Languages we care about — tweets in other languages are likely false positives
RELEVANT_LANGS = {"en", "in", "id", "it", "und"}  # English, Indonesian, Italian, undefined


def _classify_intent(text: str) -> tuple[str, float]:
    """Classify tweet intent as lead, informational, or spam."""
    lower = text.lower()

    # Spam detection — single keyword enough if it's strong
    spam_count = sum(1 for kw in SPAM_KEYWORDS if kw in lower)
    if spam_count >= 2:
        return "spam", min(0.5 + spam_count * 0.15, 0.95)
    if spam_count == 1 and any(s in lower for s in ["🚀", "💰", "join", "t.me/"]):
        return "spam", 0.7

    lead_count = sum(1 for kw in LEAD_KEYWORDS if kw in lower)
    if lead_count >= 2:
        return "lead", min(0.4 + lead_count * 0.12, 0.95)
    if lead_count == 1:
        return "lead", 0.45

    return "informational", 0.3


def _extract_matched_keywords(text: str, keywords: list[str]) -> list[str]:
    """Extract which monitor keywords matched the tweet text."""
    lower = text.lower()
    return [kw for kw in keywords if kw.lower() in lower]


class XMonitorService:
    """Background service that polls X search/recent for keyword matches."""

    def __init__(self, db_pool: Any | None = None) -> None:
        self._db_pool = db_pool
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._digest_task: asyncio.Task[None] | None = None
        self._since_id: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._credits_warned: bool = False
        self._keywords = [kw.strip() for kw in settings.x_monitor_keywords.split(",") if kw.strip()]

    @property
    def bearer_token(self) -> str | None:
        """Bearer token."""
        return settings.x_bearer_token

    def _build_query(self) -> str:
        """Build X API search query from configured keywords."""
        keyword_parts = " OR ".join(f'"{kw}"' for kw in self._keywords)
        return f"({keyword_parts}) -is:retweet (lang:en OR lang:id OR lang:it)"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _search_recent(self) -> dict[str, Any]:
        """Call GET /2/tweets/search/recent with Bearer token."""
        client = await self._get_client()
        url = "https://api.x.com/2/tweets/search/recent"
        params: dict[str, str] = {
            "query": self._build_query(),
            "max_results": "20",
            "tweet.fields": "created_at,author_id,public_metrics,lang",
            "expansions": "author_id",
            "user.fields": "name,username,description,public_metrics",
        }
        if self._since_id:
            params["since_id"] = self._since_id

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        resp = await client.get(url, params=params, headers=headers)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("retry-after", "60"))
            logger.warning(f"X API rate limited, retrying in {retry_after}s")
            await asyncio.sleep(retry_after)
            return {"data": [], "meta": {}}

        if resp.status_code == 402:
            if not self._credits_warned:
                logger.warning("X API credits depleted — monitor paused until credits renew")
                self._credits_warned = True
            return {"data": [], "meta": {}}

        if resp.status_code != 200:
            logger.error(f"X API search error {resp.status_code}: {resp.text}")
            return {"data": [], "meta": {}}

        self._credits_warned = False
        return resp.json()

    async def _save_tweet(
        self,
        tweet: dict[str, Any],
        author: dict[str, Any] | None,
        matched: list[str],
        intent: str,
        lead_score: float,
    ) -> int | None:
        """Save tweet to x_monitored_tweets table."""
        if not self._db_pool:
            return None

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO x_monitored_tweets
                        (tweet_id, author_id, author_handle, author_name, text,
                         matched_keywords, intent, lead_score, tweet_created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (tweet_id) DO NOTHING
                    RETURNING id
                    """,
                    tweet["id"],
                    tweet.get("author_id", ""),
                    author.get("username", "") if author else "",
                    author.get("name", "") if author else "",
                    tweet.get("text", ""),
                    matched,
                    intent,
                    lead_score,
                    datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
                    if tweet.get("created_at")
                    else datetime.now(timezone.utc),
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"Failed to save tweet {tweet.get('id')}: {e}")
            return None

    async def _create_lead(
        self, tweet: dict[str, Any], author: dict[str, Any] | None, tweet_row_id: int,
    ) -> int | None:
        """Create CRM client record for high-intent leads."""
        if not self._db_pool or not author:
            return None

        handle = author.get("username", "")
        name = author.get("name", handle)

        try:
            async with self._db_pool.acquire() as conn:
                # Check if lead already exists for this X handle
                existing = await conn.fetchrow(
                    "SELECT id FROM clients WHERE notes LIKE $1",
                    f"%@{handle}%",
                )
                if existing:
                    # Link tweet to existing client
                    await conn.execute(
                        "UPDATE x_monitored_tweets SET client_id = $1 WHERE id = $2",
                        existing["id"],
                        tweet_row_id,
                    )
                    return existing["id"]

                # Create new lead
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, status, lead_source, notes, tags, created_at)
                    VALUES ($1, 'prospect', 'x_social_listening', $2, $3, NOW())
                    RETURNING id
                    """,
                    name,
                    f"X/Twitter lead: @{handle} — {tweet.get('text', '')[:200]}",
                    ["x-lead", "social-listening"],
                )

                if client_id:
                    await conn.execute(
                        "UPDATE x_monitored_tweets SET client_id = $1 WHERE id = $2",
                        client_id,
                        tweet_row_id,
                    )
                return client_id
        except Exception as e:
            logger.error(f"Failed to create lead for @{handle}: {e}")
            return None

    async def _notify_telegram(
        self,
        tweet: dict[str, Any],
        author: dict[str, Any] | None,
        matched: list[str],
        intent: str,
        lead_score: float,
    ) -> None:
        """Send Telegram notification for lead tweets."""
        if not settings.admin_telegram_chat_id:
            return

        handle = author.get("username", "unknown") if author else "unknown"
        name = author.get("name", handle) if author else handle
        followers = author.get("public_metrics", {}).get("followers_count", 0) if author else 0
        text_preview = tweet.get("text", "")[:280]
        tweet_url = f"https://x.com/{handle}/status/{tweet['id']}"

        msg = (
            f"🐦 *X Lead Detected*\n\n"
            f"@{handle} ({name}):\n"
            f"_{text_preview}_\n\n"
            f"*Keywords:* {', '.join(matched)}\n"
            f"*Followers:* {followers:,}\n"
            f"*Intent:* {intent} ({lead_score:.2f})\n\n"
            f"[View Tweet]({tweet_url})"
        )

        try:
            from backend.services.integrations.telegram_bot_service import telegram_bot

            await telegram_bot.send_message(
                chat_id=settings.admin_telegram_chat_id,
                text=msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send X lead Telegram notification: {e}")

    async def _poll_once(self) -> int:
        """Execute one polling cycle. Returns count of new tweets processed."""
        result = await self._search_recent()
        tweets = result.get("data", [])
        if not tweets:
            return 0

        # Build author lookup from includes
        authors_list = result.get("includes", {}).get("users", [])
        authors = {u["id"]: u for u in authors_list}

        # Update since_id for next poll
        newest_id = result.get("meta", {}).get("newest_id")
        if newest_id:
            self._since_id = newest_id

        processed = 0
        skipped = 0
        for tweet in tweets:
            # Skip tweets in irrelevant languages (e.g. Turkish "kitap" = book)
            tweet_lang = tweet.get("lang", "und")
            if tweet_lang not in RELEVANT_LANGS:
                skipped += 1
                continue

            author = authors.get(tweet.get("author_id"))
            matched = _extract_matched_keywords(tweet.get("text", ""), self._keywords)
            intent, lead_score = _classify_intent(tweet.get("text", ""))

            # Skip spam — don't waste DB space
            if intent == "spam":
                skipped += 1
                continue

            tweet_row_id = await self._save_tweet(tweet, author, matched, intent, lead_score)

            if intent == "lead" and lead_score >= 0.45 and tweet_row_id:
                await self._create_lead(tweet, author, tweet_row_id)
                await self._notify_telegram(tweet, author, matched, intent, lead_score)

            processed += 1

        if skipped > 0:
            logger.info(f"🐦 X Monitor: skipped {skipped} irrelevant/spam tweets")

        return processed

    # ── Digest (Telegram) ──────────────────────────────────────────

    async def _get_undigested_tweets(self) -> list[dict[str, Any]]:
        """Get tweets captured since last digest that haven't been posted yet."""
        if not self._db_pool:
            return []

        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tweet_id, author_handle, author_name,
                       substring(text, 1, 100) as text_preview,
                       matched_keywords, intent, lead_score
                FROM x_monitored_tweets
                WHERE digested = false
                ORDER BY lead_score DESC, created_at DESC
                LIMIT 20
                """,
            )
            return [dict(r) for r in rows]

    async def _mark_digested(self, tweet_ids: list[int]) -> None:
        """Mark tweets as included in a digest."""
        if not self._db_pool or not tweet_ids:
            return
        async with self._db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE x_monitored_tweets SET digested = true WHERE id = ANY($1)",
                tweet_ids,
            )

    def _compose_telegram_digest(self, tweets: list[dict[str, Any]]) -> str:
        """Compose a Telegram digest message from recent monitored tweets."""
        leads = [t for t in tweets if t["intent"] == "lead"]
        others = [t for t in tweets if t["intent"] != "lead"]

        lines: list[str] = []
        lines.append("🔍 *X Social Listening — Digest*\n")

        if leads:
            lines.append(f"🎯 *{len(leads)} lead(s):*")
            for t in leads[:5]:
                handle = t["author_handle"]
                preview = t["text_preview"][:80].replace("\n", " ")
                score = t["lead_score"]
                tweet_url = f"https://x.com/{handle}/status/{t['tweet_id']}"
                lines.append(f"• @{handle} ({score:.0%}): _{preview}_")
                lines.append(f"  [View]({tweet_url})")
            lines.append("")

        if others:
            lines.append(f"📊 *{len(others)} mention(s):*")
            for t in others[:5]:
                handle = t["author_handle"]
                kws = ", ".join(t["matched_keywords"][:3]) if t["matched_keywords"] else "—"
                tweet_url = f"https://x.com/{handle}/status/{t['tweet_id']}"
                lines.append(f"• @{handle} — {kws} [View]({tweet_url})")
            lines.append("")

        remaining = len(tweets) - min(len(leads), 5) - min(len(others), 5)
        if remaining > 0:
            lines.append(f"_{remaining} more not shown_")

        lines.append(f"\n📈 Total: {len(tweets)} tweets | {len(leads)} leads")

        return "\n".join(lines)

    async def _send_digest_telegram(self, text: str) -> None:
        """Send digest message to admin Telegram."""
        if not settings.admin_telegram_chat_id:
            logger.warning("Digest: no admin_telegram_chat_id configured")
            return

        try:
            from backend.services.integrations.telegram_bot_service import telegram_bot

            await telegram_bot.send_message(
                chat_id=settings.admin_telegram_chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send digest to Telegram: {e}")

    async def _post_digest(self) -> None:
        """Compose and send a digest via Telegram (private, not public tweet)."""
        tweets = await self._get_undigested_tweets()
        if not tweets:
            logger.info("🐦 Digest: no new tweets to report")
            return

        digest_text = self._compose_telegram_digest(tweets)
        await self._send_digest_telegram(digest_text)

        tweet_ids = [t["id"] for t in tweets]
        await self._mark_digested(tweet_ids)
        logger.info(f"🐦 Digest sent to Telegram with {len(tweets)} tweets")

    async def _digest_loop(self) -> None:
        """Background loop that posts a digest every N hours."""
        interval = settings.x_monitor_digest_interval_hours * 3600
        logger.info(
            f"🐦 X Digest loop started: posting every {settings.x_monitor_digest_interval_hours}h",
        )
        # Wait for first interval before posting (let tweets accumulate)
        await asyncio.sleep(interval)
        while self._running:
            try:
                await self._post_digest()
            except Exception as e:
                logger.error(f"X Digest error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    # ── Main loops ───────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Main polling loop."""
        interval = settings.x_monitor_interval_seconds
        logger.info(
            f"🐦 X Monitor started: polling every {interval}s with {len(self._keywords)} keywords",
        )
        while self._running:
            try:
                count = await self._poll_once()
                if count > 0:
                    logger.info(f"🐦 X Monitor: processed {count} new tweets")
            except Exception as e:
                logger.error(f"X Monitor poll error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def start(self) -> None:
        """Start the background polling task and digest loop."""
        if not self.bearer_token:
            logger.warning("X Monitor disabled: X_BEARER_TOKEN not set")
            return
        if not settings.x_monitor_enabled:
            logger.info("X Monitor disabled via X_MONITOR_ENABLED=false")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("🐦 X Monitor background task created")

        # Start digest loop if enabled
        if settings.x_monitor_digest_enabled:
            self._digest_task = asyncio.create_task(self._digest_loop())
            logger.info("🐦 X Digest loop created")

    async def stop(self) -> None:
        """Stop the background polling task and digest loop."""
        self._running = False
        for task in (self._task, self._digest_task):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("🐦 X Monitor stopped")

    async def get_stats(self) -> dict[str, Any]:
        """Get monitoring statistics."""
        if not self._db_pool:
            return {"total": 0, "leads": 0, "responded": 0}

        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE intent = 'lead') as leads,
                    COUNT(*) FILTER (WHERE responded = true) as responded,
                    COUNT(*) FILTER (WHERE client_id IS NOT NULL) as linked_clients
                FROM x_monitored_tweets
                """,
            )
            return (
                dict(row) if row else {"total": 0, "leads": 0, "responded": 0, "linked_clients": 0}
            )

    async def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent monitored tweets."""
        if not self._db_pool:
            return []

        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tweet_id, author_handle, author_name, text,
                       matched_keywords, intent, lead_score, responded,
                       client_id, created_at, tweet_created_at
                FROM x_monitored_tweets
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]
