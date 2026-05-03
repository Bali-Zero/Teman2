"""Service layer — external dependencies injected into graph nodes."""

from nuzantara_graph.services.llm_gateway import LLMGateway, LLMResponse
from nuzantara_graph.services.vector_store import VectorStore
from nuzantara_graph.services.kg_store import KGStore
from nuzantara_graph.services.cache import SemanticCache
from nuzantara_graph.services.embeddings import EmbeddingsService
from nuzantara_graph.services.conversation_memory import ConversationMemory

__all__ = [
    "LLMGateway",
    "LLMResponse",
    "VectorStore",
    "KGStore",
    "SemanticCache",
    "EmbeddingsService",
    "ConversationMemory",
    "Services",
]


class Services:
    """Service container injected into graph nodes via config.

    Nodes access services through this container rather than
    importing globals, making testing trivial.

    For production, use `Services.from_settings(settings)` to create
    a fully-wired container from environment variables.
    """

    def __init__(
        self,
        llm: LLMGateway | None = None,
        vector_store: VectorStore | None = None,
        kg_store: KGStore | None = None,
        cache: SemanticCache | None = None,
        embeddings: EmbeddingsService | None = None,
        conversation_memory: ConversationMemory | None = None,
    ) -> None:
        self.llm = llm or LLMGateway()
        self.vector_store = vector_store or VectorStore()
        self.kg_store = kg_store or KGStore()
        self.cache = cache or SemanticCache()
        self.embeddings = embeddings
        self.conversation_memory = conversation_memory or ConversationMemory()

    @classmethod
    def from_settings(cls, settings: "Settings") -> "Services":
        """Create a fully-wired Services container from Settings.

        All external endpoints are read from environment variables
        via the Settings (Pydantic BaseSettings) object.
        """
        from nuzantara_graph.config import Settings as _Settings

        embeddings = None
        if settings.openai_api_key:
            embeddings = EmbeddingsService.from_settings(settings)

        vector_store = VectorStore.from_settings(settings, embeddings=embeddings)
        kg_store = KGStore.from_settings(settings)
        cache = SemanticCache.from_settings(settings)
        llm = LLMGateway.from_settings(settings)
        conversation_memory = ConversationMemory(redis_url=settings.redis_url)

        return cls(
            llm=llm,
            vector_store=vector_store,
            kg_store=kg_store,
            cache=cache,
            embeddings=embeddings,
            conversation_memory=conversation_memory,
        )

    async def health_check(self) -> dict:
        """Run health checks on all services."""
        results = {}

        if hasattr(self.llm, "health_check"):
            results["llm"] = await self.llm.health_check()
        if hasattr(self.vector_store, "health_check"):
            results["vector_store"] = await self.vector_store.health_check()
        if hasattr(self.kg_store, "health_check"):
            results["kg_store"] = await self.kg_store.health_check()
        if hasattr(self.cache, "health_check"):
            results["cache"] = await self.cache.health_check()
        if self.embeddings and hasattr(self.embeddings, "health_check"):
            results["embeddings"] = await self.embeddings.health_check()

        results["all_ok"] = all(
            r.get("ok", False) for r in results.values() if isinstance(r, dict)
        )
        return results

    async def close(self) -> None:
        """Close all service connections."""
        for svc in [self.llm, self.vector_store, self.kg_store, self.cache, self.conversation_memory]:
            if hasattr(svc, "close"):
                await svc.close()
