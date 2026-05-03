"""Knowledge Tools - 6 tools for KBLI, visa, and legal knowledge."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("visa_specialist", "company_setup")
    async def search_kbli(query: str, limit: int = 10) -> dict:
        """
        Search Indonesian business activity codes (KBLI 2025).

        Use when users ask about:
        - Which KBLI code fits their business
        - Business license requirements
        - Foreign investment (PMA) eligibility
        - Risk categories for business activities

        Args:
            query: Business activity description (any language - auto-translated to Indonesian)
            limit: Max results (default 10, max 20)

        Returns:
            List of matching KBLI codes with title, score, PMA status, risk category.
        """
        return await _call(
            "/api/v1/kbli-notebook/search",
            params={"query": query, "limit": min(limit, 20)},
        )

    @mcp.tool()
    @require_role("company_setup")
    async def inspect_kbli(code: str) -> dict:
        """
        Get deep details for a specific KBLI code.

        Returns licensing requirements, PMA status, risk profile,
        required permits, and related KBLI codes from the Knowledge Graph.

        Args:
            code: 5-digit KBLI code (e.g. "56101", "62010")

        Returns:
            Full KBLI detail: title, description, PMA status, licenses, related codes.
        """
        return await _call(f"/api/v1/kbli-notebook/inspect/{code}")

    @mcp.tool()
    @require_role("company_setup")
    async def chat_kbli(query: str) -> dict:
        """
        AI-powered KBLI consultation chat.

        Translates the query to Indonesian, searches KBLI semantically,
        and generates a grounded explanation with suggested follow-ups.

        Args:
            query: Question about business classification (any language)

        Returns:
            AI answer, detected KBLI codes, search results, suggested queries.
        """
        return await _call(
            "/api/v1/kbli-notebook/chat",
            method="POST",
            json={"query": query},
        )

    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant", "company_setup")
    async def ask_legal(
        question: str,
        user_id: str = "mcp-agent",
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Ask a legal question to Nuzantara's Agentic RAG system.

        Covers Indonesian law: immigration, company formation, tax,
        property, permits, visas, and general legal matters.

        IMPORTANT: Requires authentication (JWT). If no API key is set,
        this tool will return a 401 error.

        Args:
            question: Legal question (any language)
            user_id: User identifier for context tracking
            session_id: Optional session ID for conversation continuity

        Returns:
            AI-generated answer with sources, execution time, route used.
        """
        payload: dict = {"query": question, "user_id": user_id}
        if session_id:
            payload["session_id"] = session_id
        return await _call("/api/agentic-rag/query", method="POST", json=payload)

    @mcp.tool()
    @require_role("visa_specialist")
    async def list_visa_types() -> dict:
        """
        List all available visa types for Indonesia.

        Returns:
            Complete list of visa types with code, name, description, eligibility summary.
        """
        return await _call("/api/knowledge/visa-types")

    @mcp.tool()
    @require_role("visa_specialist")
    async def get_visa_details(visa_code: str) -> dict:
        """
        Get detailed information about a specific visa type.

        Args:
            visa_code: Visa type code (e.g. "kitas_investor", "kitap", "b211a")

        Returns:
            Full visa details: requirements, documents, process, timeline, costs, restrictions.
        """
        return await _call(f"/api/knowledge/visa-types/{visa_code}")

    @mcp.tool()
    async def visualize_langgraph(subgraph: Optional[str] = None) -> dict:
        """
        Get Mermaid diagram for Knowledge Graph orchestration.

        Use this to debug the reasoning flow or understand how subgraphs
        (visa, company, tax, property) are structured.

        Args:
            subgraph: Optional subgraph name (visa, company, tax, property)

        Returns:
            Mermaid string in a dict.
        """
        params = {}
        if subgraph:
            params["subgraph"] = subgraph
        return await _call("/api/kg/visualize", params=params)
