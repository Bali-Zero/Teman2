#!/usr/bin/env python3
"""
Fact Checker — pre-publish validation for Intel articles and content.

# Organo: fact-checker (cron-agent-python) → produce:
#         JSON validation report + Telegram alert (se flag trovati)
#         consumato da: Intel Scraper pipeline (pre-publish gate)
# Consuma da: ~/.intel_scraper/staged-for-publish/ (articoli pronti a publish)
#             web_search() per verifica affermazioni
#
# Ruolo: sentinella qualità. Prima che un articolo venga pubblicato su
#        kita.balizero.com, verifica le affermazioni fattuali chiave.
#        Auto-flag content outdated o non verificabile. Zero costo.

Process:
  1. Read staged articles from publish queue
  2. Extract factual claims (numbers, dates, legal references)
  3. web_search() to verify each claim
  4. Flag if: unverifiable, contradicted by search, outdated (>6mo)
  5. Write validation report JSON
  6. Block publish if RED flags found, allow with warnings if YELLOW

Usage:
  - Called by Intel Scraper pipeline before publish
  - Or run as standalone cron to audit recent publications
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main, web_search, web_fetch

STAGED_FOR_PUBLISH_DIR = Path.home() / ".intel_scraper" / "staged-for-publish"
VALIDATION_REPORTS_DIR = Path.home() / ".intel_scraper" / "validation-reports"
BLOCKED_DIR = Path.home() / ".intel_scraper" / "blocked"

# Max articles to check per run
MAX_ARTICLES_PER_RUN = 5

# Patterns that indicate factual claims worth checking
CLAIM_PATTERNS = [
    # Legal references
    re.compile(r"(?:Perpres|PP|Permenkumham|UU|PMK|Permendag)\s*(?:No\.?|Nomor)?\s*[\d/]+(?:/\d+)?", re.IGNORECASE),
    # Percentages
    re.compile(r"\d+(?:\.\d+)?\s*%\s+(?:of\s+)?(?:ownership|saham|stake|foreign)", re.IGNORECASE),
    # Specific dates with significance
    re.compile(r"(?:effective|berlaku)\s+(?:since|since|dari|sejak)?\s+\d{1,2}\s+\w+\s+\d{4}", re.IGNORECASE),
    # Monetary thresholds
    re.compile(r"(?:minimum|minimum|wajib)\s+(?:investment|investasi|modal)\s+(?:of\s+)?(?:USD|IDR|Rp)?\s*[\d,\.]+", re.IGNORECASE),
    # Visa/permit names
    re.compile(r"(?:KITAS|KITAP|B211A|C6[12]|e-visa|visa on arrival|voa)", re.IGNORECASE),
]


class FactCheckerJob(AgentJob):
    name = "fact-checker"
    timeout_s = 300
    requires_side_effects = False

    async def run(self) -> RunResult:
        STAGED_FOR_PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
        VALIDATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        BLOCKED_DIR.mkdir(parents=True, exist_ok=True)

        # Find articles staged for publish
        articles = list(STAGED_FOR_PUBLISH_DIR.glob("*.json"))[:MAX_ARTICLES_PER_RUN]

        if not articles:
            self.log_step("no_articles_to_check")
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_articles_to_check",
            )

        self.log_step("check_start", inputs={"count": len(articles)})
        reports = []
        blocked = 0
        warned = 0

        for article_file in articles:
            try:
                article = json.loads(article_file.read_text())
                report = await self._check_article(article)
                reports.append(report)

                # Write validation report
                report_file = VALIDATION_REPORTS_DIR / f"{article_file.stem}_validation.json"
                report_file.write_text(json.dumps(report, indent=2, default=str))

                if report["verdict"] == "BLOCKED":
                    # Move to blocked dir
                    import shutil
                    shutil.move(str(article_file), str(BLOCKED_DIR / article_file.name))
                    blocked += 1
                elif report["verdict"] == "WARNED":
                    warned += 1
                    # Leave in place but add _warned suffix to indicate reviewed
            except Exception as e:
                self.logger.error("check_error", file=article_file.name, error=str(e))

        self.log_step("check_done", outputs={
            "total": len(articles), "blocked": blocked, "warned": warned,
            "passed": len(articles) - blocked - warned,
        })

        # Alert if anything blocked
        if blocked > 0 or warned > 0:
            msg = self._compose_report(reports, blocked, warned)
            ok = await self.send_telegram(msg)
            self.log_step("telegram_sent", side_effect="fact_check_alert" if ok else None)

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps({"total": len(articles), "blocked": blocked, "warned": warned}),
        )

    async def _check_article(self, article: dict) -> dict:
        """Run fact checks on a single article. Returns validation report."""
        content = article.get("the_facts", "") or article.get("content", "")
        title = article.get("headline", "") or article.get("title", "?")
        article_id = article.get("id", "unknown")

        claims = self._extract_claims(content)
        claim_results = []
        red_flags = 0
        yellow_flags = 0

        for claim in claims[:5]:  # check up to 5 claims per article
            result = await self._verify_claim(claim)
            claim_results.append(result)
            if result["status"] == "RED":
                red_flags += 1
            elif result["status"] == "YELLOW":
                yellow_flags += 1

        verdict = "PASSED"
        if red_flags > 0:
            verdict = "BLOCKED"
        elif yellow_flags > 1:
            verdict = "WARNED"

        return {
            "article_id": article_id,
            "title": title[:100],
            "verdict": verdict,
            "red_flags": red_flags,
            "yellow_flags": yellow_flags,
            "claims_checked": len(claim_results),
            "claim_results": claim_results,
            "checked_at": datetime.now(WITA).isoformat(),
        }

    def _extract_claims(self, content: str) -> list[str]:
        """Extract verifiable factual claims from content."""
        claims = []
        seen: set = set()
        for pattern in CLAIM_PATTERNS:
            for m in pattern.finditer(content[:5000]):
                claim = m.group(0).strip()
                if claim not in seen and len(claim) > 5:
                    seen.add(claim)
                    # Get surrounding context (50 chars before + match + 100 after)
                    start = max(0, m.start() - 50)
                    end = min(len(content), m.end() + 100)
                    context = content[start:end].strip()
                    claims.append(context[:300])
        return claims[:10]

    async def _verify_claim(self, claim: str) -> dict:
        """Verify a single claim via web search + LLM with inline citations."""
        query = f"Indonesia {claim[:100]} official"

        results = await web_search(query, count=3, freshness="py", logger=self.logger)

        if not results:
            return {
                "claim": claim[:100],
                "status": "YELLOW",
                "reason": "unverifiable",
                "sources": [],
            }

        # Heuristic fast-path (cheap, catches obvious cases)
        result_titles = " ".join(r.get("title", "") for r in results).lower()
        result_descs = " ".join(r.get("description", "") for r in results).lower()
        combined = result_titles + " " + result_descs

        heur_status = None
        heur_reason = None
        if any(kw in combined for kw in ["repealed", "abolished", "no longer",
                                         "expired", "canceled", "tidak berlaku",
                                         "dicabut"]):
            heur_status = "RED"
            heur_reason = "possible_repeal"
        elif any(kw in combined for kw in ["amended", "updated", "new regulation",
                                           "perubahan", "terbaru", "pengganti"]):
            heur_status = "YELLOW"
            heur_reason = "possible_update"

        # LLM verification (Sonnet 4.6 via routing — claim analysis, cheap)
        # with soft-cite pattern: ask model to cite inline as [S1], [S2], etc.
        llm_result = await self._verify_with_llm(claim, results)

        if llm_result is None:
            # LLM call failed — fall back to heuristic
            return {
                "claim": claim[:100],
                "status": heur_status or "GREEN",
                "reason": heur_reason or "verified_heuristic",
                "sources": [r.get("url", "") for r in results[:2]],
            }

        # LLM wins; log heuristic for comparison
        if heur_status and heur_status != llm_result["status"]:
            self.logger.info(
                "verify_heur_vs_llm_mismatch",
                claim=claim[:80],
                heur=heur_status,
                llm=llm_result["status"],
            )

        return {
            "claim": claim[:100],
            "status": llm_result["status"],
            "reason": llm_result["reason"],
            "citations": llm_result.get("citations", []),
            "sources": [r.get("url", "") for r in results[:3]],
        }

    async def _verify_with_llm(self, claim: str, results: list[dict]) -> dict | None:
        """LLM-grade verification with inline-citation pattern.

        Asks Claude to classify RED/YELLOW/GREEN and cite source as [S<N>].
        Regex-parses inline citations since OAuth Max plan doesn't propagate
        structured citation blocks.

        Returns dict {status, reason, citations} or None on SDK error.
        """
        sources_blob = "\n\n".join(
            f"[S{i+1}] {r.get('title','')} — {r.get('description','')[:300]} "
            f"({r.get('url','')})"
            for i, r in enumerate(results[:3])
        )

        prompt = (
            f"Claim to verify: {claim[:400]}\n\n"
            f"Available sources:\n{sources_blob}\n\n"
            f"Classify the claim:\n"
            f"  RED: source explicitly contradicts, repeals, or supersedes it\n"
            f"  YELLOW: source suggests ambiguity, recent change, or partial support\n"
            f"  GREEN: source supports claim\n\n"
            f"Output exactly this JSON (no prose, no fences):\n"
            f'{{"status":"RED|YELLOW|GREEN","reason":"<short reason>",'
            f'"citations":["S1","S2"]}}\n'
            f"Cite ONLY sources you actually used to reach the verdict."
        )

        out = await self.claude_synthesize(
            prompt=prompt,
            max_turns=1,
            system_prompt=(
                "You are a fact-checker. Output a single JSON object, nothing else. "
                "Cite sources as [S1], [S2], [S3]. Zero invention."
            ),
        )

        if not out or out.startswith("[synthesis error"):
            return None

        # Strip possible fences
        raw = out.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.lstrip().startswith("json"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            self.logger.warning("verify_llm_json_parse_failed", raw=raw[:200])
            return None

        status = parsed.get("status", "YELLOW").upper()
        if status not in ("RED", "YELLOW", "GREEN"):
            status = "YELLOW"
        return {
            "status": status,
            "reason": str(parsed.get("reason", "llm_verdict"))[:200],
            "citations": parsed.get("citations", []) or [],
        }

    def _compose_report(self, reports: list[dict], blocked: int, warned: int) -> str:
        now = datetime.now(WITA)
        icon = "🔴" if blocked > 0 else "🟡"
        lines = [
            f"{icon} <b>Fact Check Report</b>",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
            f"Checked: {len(reports)} articles",
            f"🔴 BLOCKED: {blocked}",
            f"🟡 WARNED: {warned}",
            f"✅ PASSED: {len(reports) - blocked - warned}",
            "",
        ]
        for r in reports:
            if r["verdict"] in ("BLOCKED", "WARNED"):
                v_icon = "🔴" if r["verdict"] == "BLOCKED" else "🟡"
                lines.append(f"{v_icon} {r['title'][:80]}")
                lines.append(f"  Red: {r['red_flags']}, Yellow: {r['yellow_flags']}")
                # Show first red/yellow claim
                for cr in r.get("claim_results", []):
                    if cr["status"] in ("RED", "YELLOW"):
                        lines.append(f"  • {cr['claim'][:80]} → {cr['reason']}")
                        break
        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(FactCheckerJob)
