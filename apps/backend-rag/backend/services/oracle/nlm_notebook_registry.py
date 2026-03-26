"""NLM Notebook Registry — static mapping of domains to NotebookLM notebook IDs.

Each domain contains a notebook_id (UUID), a human-readable label, and a set
of keywords used by resolve_notebook() to route an arbitrary query to the
best-matching notebook.
"""

from __future__ import annotations

NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "84375bc3-12d0-4405-a774-9b89189d8c39",
        "label": "Immigration & Visa",
        "keywords": {
            "visa",
            "kitas",
            "kitap",
            "tka",
            "immigration",
            "imigrasi",
            "work permit",
            "stay permit",
            "foreigner",
            "expat",
        },
    },
    "company": {
        "notebook_id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4",
        "label": "Company & Licensing",
        "keywords": {
            "company",
            "kbli",
            "pma",
            "oss",
            "licensing",
            "nib",
            "investment",
            "business",
            "pt ",
            "perseroan",
        },
    },
    "tax": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "label": "Tax & Compliance",
        "keywords": {
            "tax",
            "compliance",
            "lkpm",
            "npwp",
            "pph",
            "ppn",
            "coretax",
            "bpjs",
            "fiscal",
            "pajak",
        },
    },
    "property": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "label": "Property & Zoning",
        "keywords": {
            "property",
            "zoning",
            "land",
            "hgb",
            "hak pakai",
            "building",
            "villa",
            "real estate",
            "leasehold",
        },
    },
    "operations": {
        "notebook_id": "3e1baa5f-680f-4499-9430-23a901576bcc",
        "label": "Operations",
        "keywords": {
            "sop",
            "team",
            "pricing",
            "crm",
            "workflow",
            "competitor",
        },
    },
    "editorial": {
        "notebook_id": "dd464d8f-6b8e-4543-8647-f62c498589b1",
        "label": "Editorial & Market",
        "keywords": {
            "seo",
            "content",
            "market",
            "intel",
            "trends",
            "news",
            "article",
            "editorial",
        },
    },
    "lifestyle": {
        "notebook_id": "1143b525-dd3f-40d7-a34d-2e9263b44460",
        "label": "Expat Life",
        "keywords": {
            "lifestyle",
            "expat",
            "healthcare",
            "cost of living",
            "culture",
            "digital nomad",
            "education",
            "school",
        },
    },
}


def resolve_notebook(query: str) -> dict[str, object] | None:
    """Resolve a user query to the best-matching NLM notebook.

    Lowercases the query, counts keyword hits per domain, and returns the
    domain dict (with an added ``"domain"`` key) that has the most hits.
    Returns ``None`` when no keywords match.

    Args:
        query: Free-text user query.

    Returns:
        A dict with keys ``domain``, ``notebook_id``, ``label``, ``keywords``
        for the best match, or ``None`` if nothing matches.
    """
    if not query:
        return None

    query_lower = query.lower()

    best_domain: str | None = None
    best_score: int = 0

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain is None:
        return None

    return {"domain": best_domain, **NLM_NOTEBOOKS[best_domain]}
