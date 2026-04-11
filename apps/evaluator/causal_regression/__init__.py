"""
Causal regression harness for Nuzantara RAG.

Given a git range, walks commits touching `apps/backend-rag/`, reconstructs each
commit's KB/prompt/config state from git blobs, replays a frozen eval set against
a deterministic BM25-ish mock retriever, and attributes any pass->fail transition
to one of seven root-cause categories (see `causal_diff.RootCause`).

No API keys. No network. No touching the working tree.
"""
