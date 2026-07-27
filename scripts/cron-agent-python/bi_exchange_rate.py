#!/usr/bin/env python3
"""
BI Exchange Rate Scraper — daily 07:00 WITA.

# Organo: bi-exchange-rate (cron-agent-python, browser scraper) → produce:
#         Redis cache key `bz:exchange_rate:latest` + Telegram digest
#         consumato da: CRM PricingTool, client invoices, daily-ops
# Consuma da: bi.go.id (public, no auth)
#
# Ruolo: sensore finanziario. Aggiorna tassi di cambio IDR prima dell'apertura
#         business. CRM usa questi tassi per calcoli automatici.

Fetches Bank Indonesia official exchange rates (kurs tengah BI).
Parses HTML table for USD, EUR, SGD, AUD (primary currencies for Bali Zero clients).
Stores in Redis + sends Telegram digest.
Fallback: api.exchangerate-api.com (free tier) if BI site unreachable.
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
from agent_job import AgentJob, RunResult, WITA, main
from browser_job import BrowserJob


# Currencies we care about for Bali Zero
CURRENCIES_OF_INTEREST = {"USD", "EUR", "SGD", "AUD", "GBP", "JPY", "CNY"}

# Redis key
REDIS_KEY = "bz:exchange_rate:latest"
REDIS_EXPIRY = 86400 * 2  # 48h

# BI kurs tengah URL
BI_URL = "https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx"
# Fallback: simpler BI API endpoint (JSON)
BI_API_URL = "https://www.bi.go.id/biwebservice/wskursbi.asmx/getCursTransaksiBI10"


class BiExchangeRateJob(BrowserJob):
    name = "bi-exchange-rate"
    target_url = BI_URL
    timeout_s = 120
    page_timeout_ms = 20000
    requires_side_effects = True

    async def run(self) -> RunResult:
        """Override: try BI API first (JSON), fallback to HTML scrape."""
        # PR-C4 (2026-04-30): BI native API broken since 2026-04-22; HTML primary now.
        data = await self._try_html_scrape()

        if not data:
            # Last resort: exchangerate-api.com free tier
            data = await self._try_fallback_api()

        if not data:
            await self.send_telegram(
                f"❌ <b>bi-exchange-rate</b> — tutti i sources falliti\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')}"
            )
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                error="all sources failed (BI API, HTML, fallback)",
            )

        # Store in Redis
        redis_ok = await self._store_redis(data)

        # Send Telegram digest
        msg = self._compose_message(data)
        tg_ok = await self.send_telegram(msg)
        self.log_step("telegram_send", outputs={"ok": tg_ok},
                      side_effect="exchange_rate_digest" if tg_ok else None,
                      error=None if tg_ok else "telegram_failed")

        if not tg_ok:
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                error="Telegram delivery failed",
            )

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps(data, default=str),
        )

    async def _try_bi_api(self) -> dict | None:
        """Try BI SOAP/REST API (JSON response)."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(BI_API_URL, headers={"Accept": "application/json"})
                if r.status_code != 200:
                    return None
                # BI returns XML or JSON depending on content negotiation
                text = r.text
                rates = self._parse_bi_xml(text)
                if rates:
                    self.log_step("bi_api_ok", outputs={"currencies": len(rates)})
                    return {"source": "bi_api", "rates": rates, "ts": int(time.time())}
        except Exception as e:
            self.logger.warning("bi_api_error", error=str(e))
        return None

    def _parse_bi_xml(self, text: str) -> dict[str, float] | None:
        """Parse BI XML/HTML response for kurs tengah."""
        rates: dict[str, float] = {}
        # Pattern: USD | 16,240.00 (kurs tengah)
        # XML pattern from BI API
        patterns = [
            r'<kode_valas>([A-Z]{3})</kode_valas>.*?<kurs_tengah>([\d.,]+)</kurs_tengah>',
            r'([A-Z]{3})\s*\|\s*[\d.,]+\s*\|\s*([\d.,]+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for currency, value in matches:
                if currency in CURRENCIES_OF_INTEREST:
                    try:
                        clean = value.replace(",", "").replace(".", "")
                        # BI format: 16,240.00 = 16240.00 IDR per 1 unit
                        clean_val = re.sub(r'[^\d.]', '', value)
                        rates[currency] = float(clean_val)
                    except ValueError:
                        pass
        return rates if rates else None

    async def _try_html_scrape(self) -> dict | None:
        """Fallback: scrape BI HTML page."""
        try:
            if not await self._check_robots(self.target_url):
                return None
            await self.random_delay(1.0, 2.0)
            page = await self.fetch_page(self.target_url)
            html = page["html"]
            rates = self._parse_bi_html(html)
            if rates:
                self.log_step("bi_html_ok", outputs={"currencies": len(rates)})
                return {"source": "bi_html", "rates": rates, "ts": int(time.time())}
        except Exception as e:
            self.logger.warning("bi_html_error", error=str(e))
        return None

    def _parse_bi_html(self, html: str) -> dict[str, float] | None:
        """Extract kurs tengah from BI HTML table."""
        rates: dict[str, float] = {}
        # Match table rows with currency codes
        row_pattern = re.compile(
            r'<tr[^>]*>.*?([A-Z]{3})\s*(?:Dolar|Euro|Dollar|Pound|Yen|Yuan|Frank|Ringgit|Bath)?'
            r'.*?(?:kurs[-_]tengah|tengah).*?([\d.,]+)',
            re.IGNORECASE | re.DOTALL
        )
        for m in row_pattern.finditer(html[:50000]):
            currency = m.group(1)
            if currency in CURRENCIES_OF_INTEREST:
                try:
                    rates[currency] = float(m.group(2).replace(",", ""))
                except ValueError:
                    pass
        return rates if rates else None

    async def _try_fallback_api(self) -> dict | None:
        """Last resort: free exchangerate-api.com (IDR base)."""
        try:
            import httpx
            url = "https://open.er-api.com/v6/latest/USD"
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                data = r.json()
                idr_per_usd = data.get("rates", {}).get("IDR")
                if not idr_per_usd:
                    return None
                # Convert: all rates → IDR
                rates = {}
                base_rates = data.get("rates", {})
                for cur in CURRENCIES_OF_INTEREST:
                    if cur in base_rates and base_rates[cur] > 0:
                        rates[cur] = idr_per_usd / base_rates[cur]
                rates["USD"] = idr_per_usd
                self.log_step("fallback_api_ok", outputs={"currencies": len(rates)})
                return {"source": "fallback_api", "rates": rates, "ts": int(time.time())}
        except Exception as e:
            self.logger.warning("fallback_api_error", error=str(e))
        return None

    async def _store_redis(self, data: dict) -> bool:
        """Store rates in Redis with 48h expiry."""
        try:
            import subprocess
            payload = json.dumps(data)
            result = subprocess.run(
                ["redis-cli", "SET", REDIS_KEY, payload, "EX", str(REDIS_EXPIRY)],
                capture_output=True, text=True, timeout=5
            )
            ok = result.returncode == 0 and "OK" in result.stdout
            self.log_step("redis_store", outputs={"ok": ok, "key": REDIS_KEY},
                          side_effect="redis_exchange_rate" if ok else None)
            return ok
        except Exception as e:
            self.logger.error("redis_store_error", error=str(e))
            return False

    def _compose_message(self, data: dict) -> str:
        now = datetime.now(WITA)
        source_tag = {"bi_api": "BI API", "bi_html": "BI HTML", "fallback_api": "Fallback"}.get(
            data.get("source", ""), data.get("source", "?")
        )
        rates = data.get("rates", {})
        lines = [
            f"💱 <b>Kurs BI</b> — {now.strftime('%Y-%m-%d %H:%M WITA')}",
            f"<i>Source: {source_tag}</i>",
            "",
        ]
        # Priority order
        for cur in ["USD", "EUR", "SGD", "AUD", "GBP", "JPY", "CNY"]:
            if cur in rates:
                rate = rates[cur]
                if cur == "JPY":
                    lines.append(f"🇯🇵 {cur}/IDR: {rate:,.2f}")
                else:
                    lines.append(f"{'🇺🇸' if cur=='USD' else '🇪🇺' if cur=='EUR' else '🇸🇬' if cur=='SGD' else '🇦🇺' if cur=='AUD' else '🇬🇧' if cur=='GBP' else '🇨🇳'} {cur}/IDR: {rate:,.2f}")

        lines.append("")
        lines.append(f"📦 Cached: <code>{REDIS_KEY}</code>")
        return "\n".join(lines)

    def scrape(self, html: str, text: str) -> dict:
        """Not used — run() is fully overridden."""
        return {}


if __name__ == "__main__":
    main(BiExchangeRateJob)
