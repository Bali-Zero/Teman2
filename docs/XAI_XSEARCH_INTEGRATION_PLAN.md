# xAI x_search Integration Plan — War Room Pipeline

**Date:** 2026-03-29
**Author:** AI Team
**Status:** READY TO IMPLEMENT
**Target file:** `apps/war-room/agents/01_grok_scraper.py`

---

## 1. API Setup Steps

### 1.1 Account Registration

1. Go to [accounts.x.ai/sign-up](https://accounts.x.ai/sign-up?redirect=cloud-console)
2. Create an xAI account (no X Premium required, no credit card required for signup)
3. You receive **$25 free promotional credits** immediately (expire 30 days after creation)
4. Generate an API key at [console.x.ai/team/default/api-keys](https://console.x.ai/team/default/api-keys)
5. Set the environment variable:
   ```bash
   export XAI_API_KEY="xai-..."
   ```

### 1.2 Activate Data Sharing Program ($150/month free credits)

**Requirements:**

- Team must have already spent a minimum of **$5** on the API before opting in
- Team must not be based in excluded regions (list not publicly documented)
- Only team admins can enable data sharing

**Steps:**

1. Spend at least $5 on the API (use the $25 signup credits — run a few test queries)
2. Go to **console.x.ai** → **Settings** → **Billing** → **Credits Section**
3. Enable **"Share API Inputs for Model Training"**
4. Review and accept terms, confirm enrollment
5. Credits appear within 24 hours and **refresh monthly**

**IMPORTANT — IRREVERSIBLE:**
Once opted in, the team **cannot opt out**. xAI uses API interactions (prompts + responses) to improve models.

**Mitigation:** Create a dedicated team (e.g., "war-room-intel") for data sharing. Keep a separate team for sensitive/confidential queries with data sharing disabled.

### 1.3 Monthly Credit Budget

| Source                  | Amount         | Frequency                |
| ----------------------- | -------------- | ------------------------ |
| Signup credits          | $25            | One-time (30-day expiry) |
| Data sharing            | $150           | Monthly (recurring)      |
| **Total (first month)** | **$175**       |                          |
| **Total (subsequent)**  | **$150/month** |                          |

### 1.4 Our Estimated Monthly Usage

| Tool                          | Estimated calls/month | Cost per 1K calls | Monthly cost     |
| ----------------------------- | --------------------- | ----------------- | ---------------- |
| x_search                      | ~300 (10 queries/day) | $5.00             | $1.50            |
| web_search                    | ~150 (5 queries/day)  | $5.00             | $0.75            |
| Input tokens (grok-4-1-fast)  | ~5M                   | $0.20/M           | $1.00            |
| Output tokens (grok-4-1-fast) | ~2M                   | $0.50/M           | $1.00            |
| **Total estimated**           |                       |                   | **~$4.25/month** |

With $150/month in free credits, this is effectively **$0/month** for our war-room use case.
The remaining ~$145 can be used for other xAI integrations (web_search for intel scraper, etc.).

---

## 2. Technical Documentation

### 2.1 API Endpoint

```
POST https://api.x.ai/v1/responses
```

**Authentication:** Bearer token in `Authorization` header.

**NOTE:** The old `POST /v1/chat/completions` with `search_parameters` is **deprecated** (since Jan 12, 2026). Use the Responses API exclusively.

### 2.2 x_search Tool Parameters

| Parameter                    | Type     | Description                          | Limits                                   |
| ---------------------------- | -------- | ------------------------------------ | ---------------------------------------- |
| `type`                       | string   | Always `"x_search"`                  | Required                                 |
| `allowed_x_handles`          | string[] | Only search posts from these handles | Max 10, mutually exclusive with excluded |
| `excluded_x_handles`         | string[] | Exclude posts from these handles     | Max 10, mutually exclusive with allowed  |
| `from_date`                  | string   | Start date (ISO8601: `YYYY-MM-DD`)   | Optional                                 |
| `to_date`                    | string   | End date (ISO8601: `YYYY-MM-DD`)     | Optional                                 |
| `enable_image_understanding` | bool     | Analyze images in posts              | Increases token usage                    |
| `enable_video_understanding` | bool     | Analyze videos in posts              | Increases token usage                    |

### 2.3 web_search Tool Parameters

| Parameter                    | Type     | Description               | Limits                                  |
| ---------------------------- | -------- | ------------------------- | --------------------------------------- |
| `type`                       | string   | Always `"web_search"`     | Required                                |
| `allowed_domains`            | string[] | Only search these domains | Max 5, mutually exclusive with excluded |
| `excluded_domains`           | string[] | Exclude these domains     | Max 5, mutually exclusive with allowed  |
| `enable_image_understanding` | bool     | Analyze images on pages   | Increases token usage                   |

### 2.4 Model Compatibility

| Model                         | Input $/M | Output $/M | Cached $/M | Notes                        |
| ----------------------------- | --------- | ---------- | ---------- | ---------------------------- |
| `grok-4.20-reasoning`         | $2.00     | $6.00      | $0.20      | Flagship, 2M context         |
| `grok-4-1-fast-reasoning`     | $0.20     | $0.50      | $0.05      | **Recommended for war-room** |
| `grok-4-1-fast-non-reasoning` | $0.20     | $0.50      | $0.05      | Cheaper, no reasoning        |

All models: **2M context window**, 4M TPM, 600 RPM rate limit.

### 2.5 Response Schema

```json
{
  "id": "resp_abc123",
  "object": "response",
  "status": "completed",
  "model": "grok-4-1-fast-reasoning",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "People are discussing xAI's latest...[1](https://x.com/...)...",
          "annotations": [
            {
              "type": "url_citation",
              "url": "https://x.com/user/status/123456",
              "title": "1",
              "start_index": 37,
              "end_index": 76
            }
          ]
        }
      ]
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 500,
    "total_tokens": 650,
    "prompt_tokens_details": {
      "text_tokens": 150,
      "cached_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 200
    },
    "cost_in_usd_ticks": 4500000,
    "num_sources_used": 5
  }
}
```

**Citation types:** `url_citation` with `web_citation` or `x_citation` sub-types depending on tool used.

**Cost conversion:** 1 USD = 10,000,000,000 ticks. `cost_in_usd_ticks / 10_000_000_000 = USD`.

### 2.6 Curl Examples

**x_search — Basic:**

```bash
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "grok-4-1-fast-reasoning",
    "input": [
      {
        "role": "user",
        "content": "What are expats saying about KITAS visa delays in Bali on X in the last 3 days?"
      }
    ],
    "tools": [
      {
        "type": "x_search",
        "from_date": "2026-03-26",
        "to_date": "2026-03-29"
      }
    ]
  }'
```

**x_search — Filtered by handles:**

```bash
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "grok-4-1-fast-reasoning",
    "input": [
      {
        "role": "user",
        "content": "Latest posts about Indonesian business regulations"
      }
    ],
    "tools": [
      {
        "type": "x_search",
        "excluded_x_handles": ["elonmusk"],
        "from_date": "2026-03-26"
      }
    ]
  }'
```

**Dual tools (x_search + web_search) — the model decides which to use:**

```bash
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
    "model": "grok-4-1-fast-reasoning",
    "input": [
      {
        "role": "user",
        "content": "Find social media complaints and news articles about Coretax DJP errors in Indonesia, last 72 hours"
      }
    ],
    "tools": [
      {"type": "x_search", "from_date": "2026-03-26"},
      {"type": "web_search", "allowed_domains": ["cnbcindonesia.com", "ddtc.co.id", "bisnis.com", "kompas.com", "detik.com"]}
    ]
  }'
```

### 2.7 Rate Limits

| Limit                          | Value     |
| ------------------------------ | --------- |
| Tokens per minute (TPM)        | 4,000,000 |
| Requests per minute (RPM)      | 600       |
| Tools per request              | 128 (max) |
| x_search handles per request   | 10 (max)  |
| web_search domains per request | 5 (max)   |

---

## 3. Code Changes — `01_grok_scraper.py`

### 3.1 New Fallback Chain

```
xAI x_search (API, primary)
  → Exa (neural search, secondary)
    → Chrome CDP (browser automation, last resort)
```

Currently the chain is `Exa → CDP`. We add xAI as the **primary** method, pushing Exa to secondary.

### 3.2 Python Implementation

Add this function to `01_grok_scraper.py`:

```python
import httpx
from datetime import datetime

XAI_API_URL = "https://api.x.ai/v1/responses"
XAI_MODEL = "grok-4-1-fast-reasoning"


def scrape_social_via_xai(api_key: str, queries: list[str], cutoff: datetime) -> list[dict]:
    """
    Primary scraper: xAI x_search API for X/Twitter social sentiment.
    Uses x_search for social + web_search for Indonesian news.
    Returns results in the same format as Exa functions.
    """
    if not api_key:
        return []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    from_date = cutoff.strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    results = []

    for query in queries:
        try:
            payload = {
                "model": XAI_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligence analyst. Extract social media posts "
                            "about the given topic. Return a JSON array of objects with fields: "
                            "text, author, url, sentiment (positive/negative/neutral), "
                            "pain_point (one-line summary or null). "
                            "Return ONLY the JSON array, no markdown."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "tools": [
                    {
                        "type": "x_search",
                        "from_date": from_date,
                        "to_date": to_date,
                    }
                ],
            }

            # Sync httpx for compatibility with existing pipeline
            resp = httpx.post(
                XAI_API_URL,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract output text from Responses API format
            output_text = ""
            annotations = []
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text = content.get("text", "")
                            annotations = content.get("annotations", [])

            # Try to parse structured JSON from model output
            parsed = _parse_xai_response(output_text, annotations)
            results.extend(parsed)

            # Track cost
            usage = data.get("usage", {})
            cost_ticks = usage.get("cost_in_usd_ticks", 0)
            cost_usd = cost_ticks / 10_000_000_000
            sources = usage.get("num_sources_used", 0)
            print(
                f"  [xai-x_search] {query[:55]}... "
                f"→ {len(parsed)} results, {sources} sources, ${cost_usd:.4f}",
                file=sys.stderr,
            )

        except httpx.HTTPStatusError as e:
            print(f"  [xai-x_search] HTTP {e.response.status_code}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"  [xai-x_search] error: {e}", file=sys.stderr)

    return results


def scrape_news_via_xai(api_key: str, queries: list[str], cutoff: datetime) -> list[dict]:
    """
    xAI web_search for Indonesian news sources.
    Filters to our trusted Indonesian news domains.
    """
    if not api_key:
        return []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    from_date = cutoff.strftime("%Y-%m-%d")
    results = []

    # Split NEWS_DOMAINS into batches of 5 (API limit)
    domain_batches = [NEWS_DOMAINS[i:i + 5] for i in range(0, len(NEWS_DOMAINS), 5)]

    for query in queries:
        for domains in domain_batches:
            try:
                payload = {
                    "model": XAI_MODEL,
                    "input": [
                        {
                            "role": "system",
                            "content": (
                                "You are an intelligence analyst monitoring Indonesian "
                                "business regulations. Extract news articles about the topic. "
                                "Return a JSON array of objects with fields: "
                                "title, text (summary), url, timestamp (ISO format or null), "
                                "sentiment (positive/negative/neutral), "
                                "pain_point (one-line summary or null). "
                                "Return ONLY the JSON array, no markdown."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                    "tools": [
                        {
                            "type": "web_search",
                            "allowed_domains": domains,
                        }
                    ],
                }

                resp = httpx.post(
                    XAI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()

                output_text = ""
                annotations = []
                for item in data.get("output", []):
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                output_text = content.get("text", "")
                                annotations = content.get("annotations", [])

                parsed = _parse_xai_response(output_text, annotations, source="news")
                results.extend(parsed)

                print(
                    f"  [xai-web_search] {query[:40]}... [{','.join(domains[:2])}...] "
                    f"→ {len(parsed)}",
                    file=sys.stderr,
                )

            except Exception as e:
                print(f"  [xai-web_search] error: {e}", file=sys.stderr)

    return results


def _parse_xai_response(
    output_text: str,
    annotations: list[dict],
    source: str = "social",
) -> list[dict]:
    """
    Parse xAI response into our standard result format.
    Tries JSON parsing first, falls back to annotation extraction.
    """
    results = []

    # Attempt 1: Parse structured JSON from model output
    if "[" in output_text:
        try:
            json_str = output_text[output_text.find("["):output_text.rfind("]") + 1]
            raw_items = json.loads(json_str)
            for item in raw_items:
                results.append({
                    "source": source,
                    "platform": "xai-x_search" if source == "social" else "xai-web_search",
                    "text": item.get("text", ""),
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "url": item.get("url", ""),
                    "timestamp": item.get("timestamp", ""),
                    "sentiment": item.get("sentiment"),
                    "pain_point": item.get("pain_point"),
                })
            return results
        except (json.JSONDecodeError, KeyError):
            pass

    # Attempt 2: Extract from annotations (citations)
    if annotations:
        for ann in annotations:
            if ann.get("type") == "url_citation":
                results.append({
                    "source": source,
                    "platform": "xai-x_search" if source == "social" else "xai-web_search",
                    "text": output_text[ann.get("start_index", 0):ann.get("end_index", 0)],
                    "title": ann.get("title", ""),
                    "author": "",
                    "url": ann.get("url", ""),
                    "timestamp": "",
                    "sentiment": None,
                    "pain_point": None,
                })
        return results

    # Attempt 3: Return raw text as single result
    if output_text.strip():
        results.append({
            "source": source,
            "platform": "xai-raw",
            "text": output_text[:2000],
            "title": "",
            "author": "",
            "url": "",
            "timestamp": "",
            "sentiment": None,
            "pain_point": None,
        })

    return results
```

### 3.3 Updated `main()` with New Fallback Chain

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="War Room — Intelligence Scraper")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--window-hours", type=int, default=72)
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(hours=args.window_hours)
    print(f"\n[scraper] Intelligence Scraper", file=sys.stderr)
    print(f"   Topic:  {args.topic}", file=sys.stderr)
    print(f"   Window: {args.window_hours}h (since {cutoff.strftime('%Y-%m-%d %H:%M')})", file=sys.stderr)

    xai_key = os.environ.get("XAI_API_KEY", "")
    exa_key = os.environ.get("EXA_API_KEY", "")
    all_results = []
    mode = "unknown"

    # ── Priority 1: xAI x_search + web_search (API, structured, cheapest) ──
    if xai_key:
        mode = "xai-api"
        print(f"   Mode:   xAI Responses API (x_search + web_search)", file=sys.stderr)

        social = scrape_social_via_xai(xai_key, SOCIAL_QUERIES, cutoff)
        all_results.extend(social)
        print(f"   Social (xAI): {len(social)} results", file=sys.stderr)

        news = scrape_news_via_xai(xai_key, NEWS_QUERIES, cutoff)
        all_results.extend(news)
        print(f"   News (xAI):   {len(news)} results", file=sys.stderr)

    # ── Priority 2: Exa (neural search, highlights — good for Reddit) ──
    if exa_key:
        exa = _make_exa(exa_key)
        if not xai_key:
            mode = "exa-api"
            print(f"   Mode:   Exa API (neural search, highlights)", file=sys.stderr)
            social = scrape_social_via_exa(exa, cutoff)
            all_results.extend(social)
            print(f"   Social (Exa): {len(social)} results", file=sys.stderr)
            news = scrape_news_via_exa(exa, cutoff)
            all_results.extend(news)
            print(f"   News (Exa):   {len(news)} results", file=sys.stderr)

        # Reddit always via Exa (xAI x_search doesn't cover Reddit)
        reddit = scrape_reddit_via_exa(exa, cutoff)
        all_results.extend(reddit)
        print(f"   Reddit (Exa): {len(reddit)} results", file=sys.stderr)

    # ── Priority 3: Chrome CDP fallback (last resort) ──
    if not xai_key and not exa_key:
        mode = "xai-cdp"
        print("   Mode:   XAI CDP fallback (no API keys)", file=sys.stderr)
        all_results = scrape_via_xai_cdp(args.topic, cutoff)

    all_results = dedup(all_results)

    output = {
        "topic": args.topic,
        "scraped_at": datetime.now().isoformat(),
        "window_hours": args.window_hours,
        "mode": mode,
        "count": len(all_results),
        "breakdown": {
            "social_xai": sum(1 for r in all_results if r.get("platform", "").startswith("xai-")),
            "social_exa": sum(1 for r in all_results if r.get("platform") in ("tweet", "x-domain")),
            "reddit": sum(1 for r in all_results if r.get("platform") == "reddit"),
            "news_xai": sum(1 for r in all_results if r.get("platform") == "xai-web_search"),
            "news_exa": sum(1 for r in all_results if r.get("platform") in ("news-index", "id-domains")),
            "cdp": sum(1 for r in all_results if r.get("platform", "").startswith("xai-cdp")),
        },
        "data": all_results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n[OK] {len(all_results)} items → {args.output}", file=sys.stderr)
```

### 3.4 Environment Variables

Add to `.env` / Fly.io secrets / OpenClaw config:

```bash
# xAI API (primary scraper)
XAI_API_KEY=xai-...

# Exa API (secondary, especially for Reddit)
EXA_API_KEY=...  # already set
```

---

## 4. Architecture Decision: Why xAI x_search Beats Exa for X/Twitter

| Dimension                 | xAI x_search                               | Exa tweet category                |
| ------------------------- | ------------------------------------------ | --------------------------------- |
| X/Twitter coverage        | **Native** (real-time firehose)            | Crawled index (lag)               |
| Date filtering            | Native `from_date`/`to_date`               | `start_published_date` only       |
| Handle filtering          | `allowed_x_handles` / `excluded_x_handles` | None                              |
| Image/video understanding | Yes (built-in)                             | No                                |
| Sentiment analysis        | Model-integrated                           | Post-processing needed            |
| Cost per query            | $0.005 (tool) + ~$0.0003 (tokens)          | ~$0.005 (search)                  |
| Reddit coverage           | **None** (X only)                          | **Good** (domain filter)          |
| News coverage             | Via `web_search` (max 5 domains)           | Via `category="news"` (unlimited) |

**Decision:** Use xAI x_search as primary for X/Twitter sentiment, keep Exa for Reddit (xAI has no Reddit access) and as fallback. Use xAI web_search for Indonesian news domains (limited to 5 per request, batch as needed).

---

## 5. Monitoring

### 5.1 Check Credit Balance

Visit: [console.x.ai/team/default/billing](https://console.x.ai/team/default/billing)

Or programmatically check usage via the `cost_in_usd_ticks` field in every API response:

```python
# After each response
usage = response_json.get("usage", {})
cost_ticks = usage.get("cost_in_usd_ticks", 0)
cost_usd = cost_ticks / 10_000_000_000
logger.info(f"xAI call cost: ${cost_usd:.6f}")
```

### 5.2 Monthly Cost Tracking

Add to `01_grok_scraper.py` output:

```python
output["xai_cost_summary"] = {
    "total_calls": xai_call_count,
    "total_cost_usd": total_xai_cost,
    "estimated_monthly_at_rate": total_xai_cost * 30,  # if running daily
}
```

### 5.3 Alert on Credit Depletion

Add to war-room pipeline or cron:

```python
# Quick balance check via a minimal API call
def check_xai_credits_available(api_key: str) -> bool:
    """Verify xAI API key is valid and credits available."""
    try:
        resp = httpx.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": "grok-4-1-fast-non-reasoning",
                "input": [{"role": "user", "content": "ping"}],
                "max_output_tokens": 5,
            },
            timeout=10.0,
        )
        return resp.status_code == 200
    except Exception:
        return False
```

---

## 6. Implementation Checklist

- [ ] **Step 1:** Create xAI account at accounts.x.ai
- [ ] **Step 2:** Generate API key, store as `XAI_API_KEY`
- [ ] **Step 3:** Spend $5 in test queries (use the $25 signup credits)
- [ ] **Step 4:** Enable data sharing for the war-room team ($150/month free)
- [ ] **Step 5:** Add `XAI_API_KEY` to Pro env (`~/.zshrc` or OpenClaw config)
- [ ] **Step 6:** Implement code changes in `01_grok_scraper.py` (Section 3 above)
- [ ] **Step 7:** Test with: `python apps/war-room/agents/01_grok_scraper.py --topic "KITAS visa delays Bali" --output /tmp/test_xai.json --window-hours 72`
- [ ] **Step 8:** Verify output format matches downstream pipeline expectations
- [ ] **Step 9:** Run full war-room pipeline end-to-end
- [ ] **Step 10:** Add credit monitoring to cron (optional)

---

## 7. Risk Assessment

| Risk                          | Impact | Mitigation                                                  |
| ----------------------------- | ------ | ----------------------------------------------------------- |
| Data sharing is irreversible  | Medium | Use dedicated team, keep sensitive queries on separate team |
| Rate limiting (600 RPM)       | Low    | War-room runs max ~20 calls/session                         |
| x_search doesn't cover Reddit | Medium | Keep Exa for Reddit (already working)                       |
| web_search max 5 domains      | Low    | Batch into 2 requests (8 Indonesian domains)                |
| API key exposure              | High   | Environment variable only, never in code                    |
| Credit depletion mid-month    | Low    | $150 >> $4.25 estimated usage                               |
| xAI deprecates Responses API  | Low    | OpenAI-compatible SDK, easy migration                       |

---

## 8. Future Enhancements

1. **Dual-tool mode:** Send both `x_search` and `web_search` in a single request — let the model decide which to use based on query content (reduces total API calls)
2. **Handle monitoring:** Use `allowed_x_handles` to track specific accounts (competitors, government officials, industry influencers)
3. **Image understanding:** Enable `enable_image_understanding` for posts with infographics about regulations
4. **Collections Search:** Upload our knowledge base as an xAI collection for RAG-augmented search ($2.50/1K calls)
5. **Async migration:** When pipeline_v2 matures, convert to `httpx.AsyncClient` for concurrent queries
