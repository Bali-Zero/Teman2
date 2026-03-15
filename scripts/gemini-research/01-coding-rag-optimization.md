# Deep Research: RAG Pipeline Optimization 2026

You are researching for Nuzantara/Bali Zero — a production AI platform (FastAPI + Qdrant + LangGraph) serving immigration, tax, and business intelligence for Indonesia/Bali.

## Current Stack

- Qdrant vector DB: 9 collections, 66,595 docs, text-embedding-3-small (1536 dims)
- LLM: Gemini 2.5 Flash (primary), Claude Haiku 4.5 (KBLI chat), OpenAI (embeddings only)
- LangGraph: 5-node agentic RAG with 4 domain subgraphs (company, visa, property, tax)
- Knowledge Graph: 56K nodes, 161K edges in PostgreSQL
- Evidence scoring: 6-factor dynamic confidence (0.0-1.0)

## Research Questions

1. **Hybrid Search 2026**: What are the latest best practices for combining dense vector search + sparse (BM25) + knowledge graph traversal in a single retrieval pipeline? Specifically for Qdrant's native hybrid search capabilities.

2. **Re-ranking**: Should we add a cross-encoder re-ranker (Cohere Rerank v3, Jina Reranker v2, or open-source alternatives)? Cost/latency/quality tradeoffs for our scale (~500 queries/day).

3. **Agentic RAG patterns 2026**: What's the state-of-the-art for multi-step retrieval with tool use? Specifically: CRAG (Corrective RAG), Self-RAG, Adaptive RAG — which pattern fits our LangGraph architecture best?

4. **Embedding model evolution**: We're locked to text-embedding-3-small. Should we plan a migration to newer models (Cohere embed-v4, Voyage 3, Jina v3)? What's the migration strategy for 66K+ docs without downtime?

5. **Context window optimization**: With Gemini 2.5 Flash supporting 1M tokens, should we move from chunked retrieval to "stuff everything" for certain collections? Where's the quality/cost sweet spot?

## Output Format

For each question: current best practice, top 3 options with pros/cons, and a concrete recommendation for our scale and budget (~$40/mo infra).

Save your research to `docs/research/2026-03-15-rag-optimization.md`
