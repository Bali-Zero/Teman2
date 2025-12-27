"""
Collective Memory Event Emitter
Emette eventi SSE per memoria collettiva al frontend
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class CollectiveMemoryEmitter:
    """Emette eventi memoria collettiva via SSE"""

    async def emit_memory_stored(
        self,
        event_source: Any,
        memory_key: str,
        category: str,
        content: str,
        members: list,
        importance: float,
    ):
        """Emette evento memoria memorizzata"""
        try:
            event_data = {
                "type": "collective_memory_stored",
                "memory_key": memory_key,
                "category": category,
                "content": content,
                "members": members,
                "importance": importance,
                "timestamp": datetime.now().isoformat(),
            }

            await self._send_sse_event(event_source, event_data)
            logger.info(f"📤 Emitted collective_memory_stored: {memory_key}")
        except Exception as e:
            logger.error(f"❌ Failed to emit memory_stored: {e}")

    async def emit_preference_detected(
        self,
        event_source: Any,
        member: str,
        preference: str,
        category: str,
        context: str | None = None,
    ):
        """Emette evento preferenza rilevata"""
        try:
            event_data = {
                "type": "preference_detected",
                "member": member,
                "preference": preference,
                "category": category,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }

            await self._send_sse_event(event_source, event_data)
            logger.info(f"📤 Emitted preference_detected: {member} -> {preference}")
        except Exception as e:
            logger.error(f"❌ Failed to emit preference_detected: {e}")

    async def emit_milestone_detected(
        self,
        event_source: Any,
        member: str,
        milestone_type: str,
        date: str | None,
        message: str,
        recurring: bool = False,
    ):
        """Emette evento milestone rilevata"""
        try:
            event_data = {
                "type": "milestone_detected",
                "member": member,
                "milestone_type": milestone_type,
                "date": date,
                "message": message,
                "recurring": recurring,
                "timestamp": datetime.now().isoformat(),
            }

            await self._send_sse_event(event_source, event_data)
            logger.info(f"📤 Emitted milestone_detected: {member} -> {milestone_type}")
        except Exception as e:
            logger.error(f"❌ Failed to emit milestone_detected: {e}")

    async def emit_relationship_updated(
        self,
        event_source: Any,
        member_a: str,
        member_b: str,
        relationship_type: str,
        strength: float,
        context: str | None = None,
    ):
        """Emette evento relazione aggiornata"""
        try:
            event_data = {
                "type": "relationship_updated",
                "member_a": member_a,
                "member_b": member_b,
                "relationship_type": relationship_type,
                "strength": strength,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }

            await self._send_sse_event(event_source, event_data)
            logger.info(f"📤 Emitted relationship_updated: {member_a} <-> {member_b}")
        except Exception as e:
            logger.error(f"❌ Failed to emit relationship_updated: {e}")

    async def emit_memory_consolidated(
        self, event_source: Any, action: str, original_memories: list, new_memory: str, reason: str
    ):
        """Emette evento memoria consolidata"""
        try:
            event_data = {
                "type": "memory_consolidated",
                "action": action,
                "original_memories": original_memories,
                "new_memory": new_memory,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            }

            await self._send_sse_event(event_source, event_data)
            logger.info(f"📤 Emitted memory_consolidated: {action}")
        except Exception as e:
            logger.error(f"❌ Failed to emit memory_consolidated: {e}")

    async def _send_sse_event(self, event_source: Any, data: dict[str, Any]):
        """Invia evento SSE"""
        try:
            # Formato SSE standard
            event_str = f"data: {json.dumps(data)}\n\n"

            if hasattr(event_source, "send"):
                await event_source.send(event_str)
            elif hasattr(event_source, "write"):
                await event_source.write(event_str)
            else:
                # Fallback: usa yield se è un generator
                logger.warning("⚠️ Event source doesn't have send/write method")
        except Exception as e:
            logger.error(f"❌ Failed to send SSE event: {e}")


# Singleton globale
collective_memory_emitter = CollectiveMemoryEmitter()
