"""
Prime Nexus Service — Unified geospatial intelligence for Nuzantara.

Extracts shared logic from prime.py and dashboard.py into a single service
with a 3-layer resolution pipeline:
  Layer 1: resolve(lat, lng)  — spatial zone resolution (target < 50ms cache / < 2s cold)
  Layer 2: analyze(lat, lng)  — investment analysis with scoring (target < 3s)
  Layer 3: intelligence(bounds) — CRM overlay within bounding box (target < 3s)

Decisions:
  D1: Shared service, NOT merged router — routers stay as thin wrappers with fallback
  D2: Redis cache with geohash keys (not floating-point lat/lng)
  D3: Circuit breaker on BATARA/GISTARU (3 failures → skip 5min)
"""

import json
import logging
import os
import time
from typing import Any
from urllib.parse import urlencode

import asyncpg
import httpx

from backend.services.kbli_eye import KBLIEye

# Backward-compat re-exports: tests (and possibly external consumers) still
# import these symbols from prime_nexus_service after the #87 refactor split
# the service into geo/property/tax modules. Marked noqa so ruff F401 doesn't
# strip them; they are part of the module's public surface.
from backend.services.prime.geo_service import (  # noqa: F401
    RESTRICTED_ZONES,
    ZONE_COLORS_MAP,
    ZONE_LABELS,
    calculate_building_yield,
    encode_geohash,
    parse_tb_to_meters,
    rgb_string_to_hex,
)
from backend.services.prime.property_service import (  # noqa: F401
    calculate_investment_score,
    calculate_zone_kbli_fit,
    classify_activity,
    is_investor_relevant,
)
from backend.services.prime.tax_service import (  # noqa: F401
    calculate_property_eligibility,
    calculate_property_tax,
)

logger = logging.getLogger(__name__)

# =============================================================================
# BATARA + GISTARU API CONSTANTS
# =============================================================================
_BATARA_API_URL = "https://secure.pelayanan-dpupr.badungkab.go.id/api/certificate/point"
_BATARA_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://app.batara.badungkab.go.id/",
    "Origin": "https://app.batara.badungkab.go.id",
    "User-Agent": "Mozilla/5.0",
}

GISTARU_PROXY = "https://gistaru-proxy.atrbpn.go.id/proxy.ashx?"
GISTARU_RDTR_API = "https://gistaru.atrbpn.go.id/rdtrinteraktif/api/interactive"
GISTARU_MAPSERVER_BASE = "https://gistaru.atrbpn.go.id/arcgis/rest/services/060_RDTR_PROVINSI_BALI"
GISTARU_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gistaru.atrbpn.go.id/"}


# =============================================================================
# PrimeNexusService
# =============================================================================
class PrimeNexusService:
    """Unified geospatial intelligence service with circuit breaker.

    IMPORTANT: Use a single instance per app lifecycle (via app.state).
    The persistent HTTP client (_http_client) MUST be closed on shutdown.
    """

    def __init__(self, cache_service: Any = None, db_pool: asyncpg.Pool | None = None) -> None:
        self._cache = cache_service
        self._db_pool = db_pool
        self._kbli_eye: KBLIEye | None = None
        # Persistent HTTP client (Golden Rule #10: never create per-request)
        self._http_client: httpx.AsyncClient | None = None

        # Circuit breaker state
        self._batara_failures = 0
        self._batara_skip_until: float = 0.0
        self._gistaru_failures = 0
        self._gistaru_skip_until: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=12.0)
        return self._http_client

    async def close(self) -> None:
        """Close persistent HTTP client. Call in app lifespan shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.close()
            self._http_client = None

    def _get_kbli_eye(self) -> KBLIEye:
        if self._kbli_eye is None:
            self._kbli_eye = KBLIEye()
        return self._kbli_eye

    # ── Circuit Breaker Helpers ──────────────────────────────────────
    def _should_skip_batara(self) -> bool:
        if self._batara_failures >= 3 and time.time() < self._batara_skip_until:
            return True
        if time.time() >= self._batara_skip_until:
            self._batara_failures = 0
        return False

    def _record_batara_failure(self) -> None:
        self._batara_failures += 1
        if self._batara_failures >= 3:
            self._batara_skip_until = time.time() + 300  # skip 5 min
            logger.warning("⚡ [PrimeNexus] BATARA circuit breaker OPEN (3 failures, skip 5min)")

    def _record_batara_success(self) -> None:
        self._batara_failures = 0

    def _should_skip_gistaru(self) -> bool:
        if self._gistaru_failures >= 3 and time.time() < self._gistaru_skip_until:
            return True
        if time.time() >= self._gistaru_skip_until:
            self._gistaru_failures = 0
        return False

    def _record_gistaru_failure(self) -> None:
        self._gistaru_failures += 1
        if self._gistaru_failures >= 3:
            self._gistaru_skip_until = time.time() + 300
            logger.warning("⚡ [PrimeNexus] GISTARU circuit breaker OPEN (3 failures, skip 5min)")

    def _record_gistaru_success(self) -> None:
        self._gistaru_failures = 0

    # ── Coastline Distance Query ─────────────────────────────────────
    async def _query_sea_distance(self, lat: float, lng: float) -> float | None:
        """Calculate distance in meters from a point to the nearest coastline.

        Uses bali_coastline table (populated by import_bali_coastline.py).
        Results cached in Redis for 24h (coastline does not change).
        """
        # Check Redis cache
        gh6 = encode_geohash(lat, lng, precision=6)
        cache_key = f"prime:sea_dist:{gh6}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached is not None:
                    return float(cached) if cached != "null" else None
            except (ValueError, TypeError) as exc:
                logger.debug("[PrimeNexus] Sea distance cache parse error: %s", exc)
            except Exception:
                logger.debug("[PrimeNexus] Sea distance cache get failed")

        # PostGIS query
        pool = self._db_pool
        dist: float | None = None
        sql = (
            "SELECT ST_Distance("
            "  ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,"
            "  c.geom::geography"
            ") AS dist_m "
            "FROM bali_coastline c "
            "WHERE c.name = 'bali_main' "
            "LIMIT 1"
        )
        try:
            if pool:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(sql, lng, lat)
            else:
                db_url = os.environ.get("DATABASE_URL", "")
                if not db_url:
                    return None
                if db_url.startswith("postgres://"):
                    db_url = db_url.replace("postgres://", "postgresql://", 1)
                conn = await asyncpg.connect(db_url)
                try:
                    row = await conn.fetchrow(sql, lng, lat)
                finally:
                    await conn.close()

            if row and row["dist_m"] is not None:
                dist = round(float(row["dist_m"]), 1)
        except (asyncpg.PostgresError, OSError) as exc:
            logger.debug("[PrimeNexus] Sea distance query skipped: %s", exc)
        except Exception:
            logger.exception("[PrimeNexus] Unexpected error in sea distance query")

        # Cache result (24h)
        if self._cache:
            try:
                await self._cache.set(cache_key, str(dist) if dist is not None else "null", ttl=86400)
            except Exception:
                logger.debug("[PrimeNexus] Sea distance cache set failed")

        return dist

    # ── Layer 1: Spatial Resolution ──────────────────────────────────
    async def resolve(self, lat: float, lng: float) -> dict[str, Any]:
        """
        Resolve zoning data for a point. Pipeline: Redis → BATARA → GISTARU → PostGIS.
        Returns standardized zone resolution dict.
        """
        # 1. Check Redis cache (geohash key)
        gh = encode_geohash(lat, lng, precision=8)
        cache_key = f"prime:zone:gh:{gh}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    logger.debug("[PrimeNexus] Cache HIT for %s", cache_key)
                    result = cached if isinstance(cached, dict) else json.loads(cached)
                    result["cache_hit"] = True
                    return result
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.debug("[PrimeNexus] Cache parse failed: %s", exc)
            except Exception as exc:
                logger.debug("[PrimeNexus] Cache get failed: %s", exc)

        # 2. BATARA API (primary, Badung regency)
        batara_result = None
        if not self._should_skip_batara():
            batara_result = await self._query_batara(lat, lng)

        if batara_result:
            response = self._build_resolve_response(lat, lng, batara_result, "batara_live", 1.0)
            response = await self._enrich_resolve_response(response, lat, lng)
            await self._cache_zone(cache_key, response)
            return response

        # 3. GISTARU fallback (non-Badung areas)
        gistaru_result = None
        if not self._should_skip_gistaru():
            gistaru_result = await self._query_gistaru(lat, lng)

        if gistaru_result:
            response = self._build_resolve_response_from_gistaru(lat, lng, gistaru_result)
            response = await self._enrich_resolve_response(response, lat, lng)
            await self._cache_zone(cache_key, response)
            return response

        # 4. PostGIS fallback (ultimate)
        postgis_result = await self._query_postgis(lat, lng)
        if postgis_result:
            response = self._build_resolve_response_from_postgis(lat, lng, postgis_result)
            response = await self._enrich_resolve_response(response, lat, lng)
            await self._cache_zone(cache_key, response)
            return response

        return {
            "status": "outside_coverage",
            "lat": lat, "lng": lng,
            "zone": None,
            "cache_hit": False,
            "sea_distance_m": None,
            "message": "Coordinates outside mapped RDTR coverage.",
        }

    async def _enrich_resolve_response(
        self, response: dict[str, Any], lat: float, lng: float,
    ) -> dict[str, Any]:
        """Enrich resolve response with sea_distance_m."""
        sea_dist = await self._query_sea_distance(lat, lng)
        response["sea_distance_m"] = sea_dist
        if response.get("zone") and isinstance(response["zone"], dict):
            response["zone"]["sea_distance_m"] = sea_dist
        return response

    # ── BATARA query ─────────────────────────────────────────────────
    async def _query_batara(self, lat: float, lng: float) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            resp = await client.post(
                _BATARA_API_URL,
                json={"x": str(lng), "y": str(lat), "informationType": "RDTR"},
                headers={"Accept": "application/json", "Accept-Language": "en"},
                timeout=8.0,
            )
            if resp.status_code != 200:
                self._record_batara_failure()
                return None
            data = resp.json()
            if data.get("status") != 200:
                self._record_batara_failure()
                return None

            geom_list = data.get("data", {}).get("territorials", {}).get("geom", [])
            if not geom_list:
                self._record_batara_failure()
                return None

            self._record_batara_success()
            geom = geom_list[0]
            zone = geom.get("zone", {})
            if not zone:
                return None

            zone_code = zone.get("code", "")
            zone_name = zone.get("name", "")
            zone_color_rgb = zone.get("color", "")
            zone_definition = zone.get("definition", "")
            activities = zone.get("activities", [])

            businesses = self._extract_businesses(activities)
            hex_color = rgb_string_to_hex(zone_color_rgb) if zone_color_rgb else None

            overlays: dict[str, str] = {}
            kkop_val = geom.get("kkop_1", "")
            if kkop_val and "tidak" not in kkop_val.lower():
                overlays["kkop"] = kkop_val
            if geom.get("lp2b_2") == "Ya":
                overlays["lp2b"] = "Protected farmland (LP2B)"
            if geom.get("krb_03") and geom["krb_03"] != "Tidak Ada":
                overlays["tsunami"] = geom["krb_03"]
            if geom.get("cagbud") and geom["cagbud"] != "Tidak Ada":
                overlays["heritage"] = geom["cagbud"]
            teb_val = geom.get("teb_05", "")
            if teb_val and "tidak" not in teb_val.lower():
                overlays["evac_center"] = teb_val

            reqs = zone.get("zone_intensity_requirements", [])
            req_data = reqs[0] if reqs else {}
            location_data = geom.get("location", {})

            label_info = ZONE_LABELS.get(
                zone_code,
                {"label_en": zone_name, "desc_en": zone_definition[:120] if zone_definition else ""},
            )
            building_codes = calculate_building_yield(zone_code)

            logger.info(
                "✅ [PrimeNexus/BATARA] %s '%s' @ %s,%s — %d businesses",
                zone_code, zone_name, lat, lng, len(businesses),
            )
            return {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"] or zone_definition[:120],
                "zone_color_hex": hex_color,
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "businesses": businesses,
                "business_count": len(businesses),
                "overlays": overlays,
                "building_codes": building_codes,
                "kdb": req_data.get("maximum_kdb", "N/A"),
                "klb": req_data.get("maximum_klb", "N/A"),
                "kdh": req_data.get("mininum_kdh", "N/A"),
                "tb": req_data.get("old_building_height", "N/A"),
                "gsb": req_data.get("old_minimum_gsb", "N/A"),
                "desa": location_data.get("name", "N/A"),
            }
        except httpx.HTTPError as exc:
            logger.warning("⚠️ [PrimeNexus] BATARA HTTP error (%s,%s): %s", lat, lng, exc)
            self._record_batara_failure()
            return None
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("⚠️ [PrimeNexus] BATARA response parse error (%s,%s): %s", lat, lng, exc)
            self._record_batara_failure()
            return None
        except Exception:
            logger.exception("⚠️ [PrimeNexus] BATARA query unexpected error (%s,%s)", lat, lng)
            self._record_batara_failure()
            return None

    # ── GISTARU query ────────────────────────────────────────────────
    async def _query_gistaru(self, lat: float, lng: float) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            cities_resp = await client.get(
                f"{GISTARU_RDTR_API}/cities/51", headers=GISTARU_HEADERS, timeout=30.0,
            )
            cities_resp.raise_for_status()
            cities_body = cities_resp.json()
            cities = cities_body.get("data", cities_body) if isinstance(cities_body, dict) else cities_body

            for city in cities:
                city_id = city.get("id")
                if not city_id:
                    continue
                rdtr_resp = await client.get(
                    f"{GISTARU_RDTR_API}/rdtr/{city_id}", headers=GISTARU_HEADERS,
                )
                if rdtr_resp.status_code != 200:
                    continue
                rdtr_body = rdtr_resp.json()
                rdtr_list = rdtr_body.get("data", rdtr_body) if isinstance(rdtr_body, dict) else rdtr_body
                if not isinstance(rdtr_list, list):
                    continue

                for rdtr in rdtr_list:
                    mapserver_path = rdtr.get("url_mapserver", "")
                    if not mapserver_path:
                        continue
                    qs = urlencode({
                        "geometry": f"{lng},{lat}",
                        "geometryType": "esriGeometryPoint",
                        "spatialRel": "esriSpatialRelIntersects",
                        "outFields": "*", "returnGeometry": "false", "f": "json",
                    })
                    arcgis_base = "https://gistaru.atrbpn.go.id/arcgis/rest/services"
                    proxied = f"{GISTARU_PROXY}{arcgis_base}/{mapserver_path}/0/query?{qs}"
                    try:
                        qr = await client.get(proxied, headers=GISTARU_HEADERS, timeout=10)
                    except httpx.TimeoutException:
                        continue
                    if qr.status_code != 200:
                        continue
                    features = qr.json().get("features", [])
                    if not features:
                        continue

                    self._record_gistaru_success()
                    attrs = features[0].get("attributes", {})
                    city_name = city.get("kota_atau_kabupaten", "")
                    return {
                        "source": "gistaru_rdtr",
                        "code": attrs.get("KODZON", attrs.get("KODSZN", "N/A")),
                        "sub_zone": attrs.get("KODSZN", ""),
                        "name": attrs.get("NAMZON", attrs.get("NAMOBJ", "N/A")),
                        "sub_name": attrs.get("NAMSZN", ""),
                        "desa": attrs.get("WADMKD", "N/A"),
                        "kecamatan": attrs.get("WADMKC", ""),
                        "kabupaten": attrs.get("WADMKK", "") or city_name,
                        "kdb": "N/A", "klb": "N/A", "kdh": "N/A", "tb": "N/A", "gsb": "N/A",
                        "overlays": {
                            k: attrs.get(k)
                            for k in ("KKOP_1", "LP2B_2", "KRB_03", "TEB_05", "CAGBUD", "RESAIR", "SEMPDN", "HANKAM")
                            if attrs.get(k) and attrs.get(k) != "Tidak Ada"
                        },
                    }
        except httpx.HTTPError as exc:
            logger.warning("⚠️ [PrimeNexus] GISTARU HTTP error: %s", exc)
            self._record_gistaru_failure()
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("⚠️ [PrimeNexus] GISTARU response parse error: %s", exc)
            self._record_gistaru_failure()
        except Exception:
            logger.exception("⚠️ [PrimeNexus] GISTARU query unexpected error")
            self._record_gistaru_failure()
        return None

    # ── PostGIS query ────────────────────────────────────────────────
    async def _query_postgis(self, lat: float, lng: float) -> asyncpg.Record | None:
        pool = self._db_pool
        if not pool:
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return None
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    return await conn.fetchrow(
                        "SELECT district_name, subdistrict_name, zoning_type, allowed_kbli, "
                        "avg_price_per_are, risk_score FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                finally:
                    await conn.close()
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] PostGIS fallback failed: %s", exc)
                return None
            except Exception:
                logger.exception("[PrimeNexus] PostGIS fallback unexpected error")
                return None
        else:
            try:
                async with pool.acquire() as conn:
                    return await conn.fetchrow(
                        "SELECT district_name, subdistrict_name, zoning_type, allowed_kbli, "
                        "avg_price_per_are, risk_score FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] PostGIS pool query failed: %s", exc)
                return None
            except Exception:
                logger.exception("[PrimeNexus] PostGIS pool query unexpected error")
                return None

    # ── Price query ──────────────────────────────────────────────────
    async def query_price(self, lat: float, lng: float) -> float | None:
        """Lightweight PostGIS lookup for avg_price_per_are."""
        pool = self._db_pool
        if not pool:
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return None
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    row = await conn.fetchrow(
                        "SELECT avg_price_per_are FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                finally:
                    await conn.close()
                if row and row["avg_price_per_are"]:
                    return float(row["avg_price_per_are"])
            except (asyncpg.PostgresError, OSError, ValueError, TypeError) as exc:
                logger.debug("[PrimeNexus] Price lookup skipped: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Price lookup unexpected error")
        else:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT avg_price_per_are FROM bali_zoning_layers "
                        "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint($1, $2), 4326)) "
                        "ORDER BY risk_score DESC LIMIT 1",
                        lng, lat,
                    )
                    if row and row["avg_price_per_are"]:
                        return float(row["avg_price_per_are"])
            except (asyncpg.PostgresError, OSError, ValueError, TypeError) as exc:
                logger.debug("[PrimeNexus] Price pool lookup skipped: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Price pool lookup unexpected error")
        return None

    # ── Business extraction ──────────────────────────────────────────
    def _extract_businesses(self, activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority_cats = {"Hospitality", "F&B", "Wellness", "Creative"}
        first_pass: list[dict[str, Any]] = []
        second_pass: list[dict[str, Any]] = []
        seen_categories: dict[str, int] = {}

        for act in activities:
            pivot = act.get("pivot", {})
            if not pivot.get("i", False):
                continue
            name = act.get("name", "")
            if not name or not is_investor_relevant(name):
                continue
            category = classify_activity(name)
            if category == "Other":
                continue
            entry = {"title_en": name, "category_en": category, "pma_open": True}
            if category in priority_cats:
                first_pass.append(entry)
            else:
                second_pass.append(entry)

        merged: list[dict[str, Any]] = []
        for entry in first_pass + second_pass:
            cat = entry["category_en"]
            if seen_categories.get(cat, 0) >= 2:
                continue
            seen_categories[cat] = seen_categories.get(cat, 0) + 1
            merged.append(entry)
        return merged[:10]

    # ── Response builders ────────────────────────────────────────────
    def _build_resolve_response(
        self, lat: float, lng: float, batara: dict[str, Any], source: str, confidence: float,
    ) -> dict[str, Any]:
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": batara["zone_code"],
                "zone_name": batara["zone_name"],
                "zone_label_en": batara["zone_label_en"],
                "zone_description_en": batara["zone_description_en"],
                "zone_color_hex": batara.get("zone_color_hex"),
                "is_restricted": batara.get("is_restricted", False),
                "allowed_activities": [b["title_en"] for b in batara.get("businesses", [])],
                "restrictions": [],
                "overlays": batara.get("overlays", {}),
                "building_codes": batara.get("building_codes"),
                "source": source,
                "confidence": confidence,
            },
            "cache_hit": False,
            # Backward compat fields (flat, for prime.py wrapper)
            **{k: batara.get(k) for k in (
                "zone_code", "zone_name", "zone_label_en", "zone_description_en",
                "zone_color_hex", "is_restricted", "businesses", "business_count",
                "overlays", "building_codes", "kdb", "klb", "kdh", "tb", "gsb", "desa",
            )},
            "source": "BATARA/Badung DPUPR (official)",
        }

    def _build_resolve_response_from_gistaru(
        self, lat: float, lng: float, gistaru: dict[str, Any],
    ) -> dict[str, Any]:
        zone_code = gistaru.get("code", "N/A")
        label_info = ZONE_LABELS.get(
            zone_code, {"label_en": gistaru.get("name", ""), "desc_en": ""},
        )
        building_codes = calculate_building_yield(zone_code)
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": zone_code,
                "zone_name": gistaru.get("name", ""),
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"],
                "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "allowed_activities": [],
                "restrictions": [],
                "overlays": gistaru.get("overlays", {}),
                "building_codes": building_codes,
                "source": "gistaru_rdtr",
                "confidence": 0.7,
            },
            "cache_hit": False,
            # Backward compat
            "zone_code": zone_code,
            "zone_name": gistaru.get("name", ""),
            "zone_label_en": label_info["label_en"],
            "zone_description_en": label_info["desc_en"],
            "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
            "is_restricted": zone_code in RESTRICTED_ZONES,
            "businesses": [],
            "business_count": 0,
            "overlays": gistaru.get("overlays", {}),
            "building_codes": building_codes,
            "district": gistaru.get("kabupaten", ""),
            "subdistrict": gistaru.get("desa", ""),
            "source": "GISTARU/ATR-BPN (fallback)",
        }

    def _build_resolve_response_from_postgis(
        self, lat: float, lng: float, row: asyncpg.Record,
    ) -> dict[str, Any]:
        zone_type: str = row["zoning_type"]
        zone_code = zone_type.split(":")[0].strip()
        zone_name = zone_type.split(":", 1)[1].strip() if ":" in zone_type else zone_type
        label_info = ZONE_LABELS.get(
            zone_code, {"label_en": zone_name, "desc_en": "Contact local authorities for details"},
        )
        building_codes = calculate_building_yield(zone_code)
        return {
            "status": "found",
            "lat": lat, "lng": lng,
            "zone": {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "zone_label_en": label_info["label_en"],
                "zone_description_en": label_info["desc_en"],
                "zone_color_hex": ZONE_COLORS_MAP.get(zone_code),
                "is_restricted": zone_code in RESTRICTED_ZONES,
                "allowed_activities": [],
                "restrictions": [],
                "overlays": {},
                "building_codes": building_codes,
                "source": "postgis_cache",
                "confidence": 0.5,
            },
            "cache_hit": False,
            # Backward compat
            "zone_code": zone_code,
            "zone_name": zone_name,
            "zone_label_en": label_info["label_en"],
            "zone_description_en": label_info["desc_en"],
            "zone_color_hex": None,
            "zone_type": zone_type,
            "is_restricted": zone_code in RESTRICTED_ZONES,
            "businesses": [],
            "business_count": 0,
            "overlays": {},
            "building_codes": building_codes,
            "avg_price_per_are": float(row["avg_price_per_are"] or 0),
            "risk_score": float(row["risk_score"] or 0),
            "district": row["district_name"],
            "subdistrict": row["subdistrict_name"],
            "source": "PostGIS/GISTARU (local cache)",
        }

    # ── Layer 2: Investment Analysis ────────────────────────────────
    async def analyze(
        self,
        lat: float,
        lng: float,
        kbli_code: str | None = None,
        is_pma: bool = True,
        land_size_m2: float | None = None,
        price_idr: float | None = None,
        investor_profile: dict[str, Any] | None = None,
        geo_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Full investment analysis: resolve zone → KBLIEye → scoring → intel.
        Target: < 3s.
        """
        # Check analyze cache
        gh6 = encode_geohash(lat, lng, precision=6)
        cache_key = f"prime:analyze:{gh6}:{kbli_code or 'none'}:{is_pma}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    result = cached if isinstance(cached, dict) else json.loads(cached)
                    result["cache_hit"] = True
                    return result
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.debug("[PrimeNexus] Analyze cache parse error: %s", exc)
            except Exception:
                logger.debug("[PrimeNexus] Analyze cache get failed")

        # Step 1: Resolve zone
        resolve_result = await self.resolve(lat, lng)
        zone_data: dict[str, Any] | None = None
        zone_code: str | None = None

        if resolve_result.get("status") == "found":
            zone = resolve_result.get("zone", {})
            zone_code = resolve_result.get("zone_code") or (zone.get("zone_code") if zone else None)
            source = resolve_result.get("source", "")
            zone_source = zone.get("source", source) if zone else source

            zone_data = {
                "code": zone_code,
                "name": resolve_result.get("zone_name", ""),
                "source": zone_source,
                "desa": resolve_result.get("desa", resolve_result.get("subdistrict", "")),
                "kecamatan": resolve_result.get("district", ""),
                "kdb": resolve_result.get("kdb", "N/A"),
                "klb": resolve_result.get("klb", "N/A"),
                "kdh": resolve_result.get("kdh", "N/A"),
                "tb": resolve_result.get("tb", "N/A"),
                "gsb": resolve_result.get("gsb", "N/A"),
                "overlays": resolve_result.get("overlays", {}),
            }

        # Step 2: KBLIEye compliance (if kbli_code provided)
        kbli_result: dict[str, Any] | None = None
        kbli_state: str | None = None
        kbli_oss_risk: str | None = None

        if kbli_code:
            try:
                eye = self._get_kbli_eye()
                kd = eye.get_decision(code=kbli_code, is_pma=is_pma, location="Bali")
                audit = kd.get("audit", kd)
                kbli_state = audit.get("state", kd.get("state", "UNKNOWN"))
                kbli_oss_risk = audit.get("oss_risk") or None
                pma_logic = kd.get("pma_logic", {})
                kbli_result = {
                    "code": kd.get("kbli_2025", kbli_code),
                    "title": kd.get("title", ""),
                    "state": kbli_state,
                    "reason": audit.get("reason_code", ""),
                    "oss_risk": audit.get("oss_risk", ""),
                    "max_foreign_ownership": pma_logic.get("max_foreign_ownership", 0),
                }
            except (KeyError, ValueError, TypeError) as e:
                kbli_result = {"code": kbli_code, "state": "ERROR", "error": str(e)}
                logger.warning("[PrimeNexus] KBLIEye data error: %s", e)
            except Exception as e:
                kbli_result = {"code": kbli_code, "state": "ERROR", "error": str(e)}
                logger.exception("[PrimeNexus] KBLIEye unexpected error")

        # Step 3: ROI calculation (if land/price provided)
        roi_data: dict[str, Any] | None = None
        if zone_code and land_size_m2 and price_idr:
            roi_url = os.environ.get("ROI_CALCULATOR_URL", "http://localhost:8001/calculator")
            try:
                client = await self._get_client()
                roi_resp = await client.post(roi_url, json={
                    "land_size_m2": land_size_m2,
                    "price_total_idr": price_idr,
                    "zone_code": zone_code,
                }, timeout=10.0)
                roi_resp.raise_for_status()
                rd = roi_resp.json()
                roi_data = {
                    "golden_strategy": rd.get("golden_strategy", {}),
                    "urbanistica": rd.get("urbanistica", {}),
                    "total_investment_idr": rd.get("total_investment_idr"),
                }
            except httpx.HTTPError as e:
                roi_data = {"error": str(e)}
                logger.warning("[PrimeNexus] ROI HTTP error: %s", e)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                roi_data = {"error": str(e)}
                logger.warning("[PrimeNexus] ROI response parse error: %s", e)
            except Exception as e:
                roi_data = {"error": str(e)}
                logger.exception("[PrimeNexus] ROI calculation unexpected error")

        # Step 3b: Enrich geo_data with sea_distance_m and risk_score from resolve
        sea_dist = resolve_result.get("sea_distance_m")
        if geo_data is None:
            geo_data = {}
        if sea_dist is not None:
            geo_data["sea_distance_m"] = sea_dist
        # Inject numeric risk_score from PostGIS (if available in resolve)
        postgis_risk = resolve_result.get("risk_score")
        if postgis_risk is not None and postgis_risk != 0.5:
            geo_data["risk_score"] = postgis_risk

        # Step 4: Scoring engine
        scoring = calculate_investment_score(
            zone_data=zone_data,
            kbli_state=kbli_state,
            kbli_code=kbli_code,
            roi_data=roi_data,
            geo_data=geo_data,
            oss_risk=kbli_oss_risk,
        )

        # Step 4b: Property tax calculation
        property_tax: dict[str, Any] | None = None
        avg_price_per_are = resolve_result.get("avg_price_per_are", 0)
        njop_proxy = price_idr or (
            avg_price_per_are * (land_size_m2 / 100) if avg_price_per_are and land_size_m2 else None
        )
        if njop_proxy and njop_proxy > 0:
            kabupaten = (zone_data.get("kecamatan", "") if zone_data else "") or resolve_result.get("district", "")
            property_tax = calculate_property_tax(njop_proxy, kabupaten)

        # Step 4c: Property eligibility (only if nationality provided)
        property_eligibility: dict[str, Any] | None = None
        nationality = (investor_profile or {}).get("nationality")
        if nationality:
            property_eligibility = calculate_property_eligibility(
                nationality=nationality,
                zone_code=zone_code,
                njop_total_idr=njop_proxy,
            )

        # Step 5: Intel articles (best-effort)
        intel_articles: list[dict[str, Any]] = []
        if zone_code:
            subdistrict = zone_data.get("desa", "Bali") if zone_data else "Bali"
            intel_articles = await self._search_intel(zone_code, subdistrict)

        # Build verdict
        verdict_label = scoring["verdict"]
        risk_map = {"GREEN": "LOW", "YELLOW": "MEDIUM", "RED": "HIGH"}

        result: dict[str, Any] = {
            "status": "analyzed",
            "coordinates": {"lat": lat, "lng": lng},
            "zone": zone_data,
            "kbli": kbli_result,
            "roi": roi_data,
            "verdict": {
                "can_invest": scoring["can_invest"],
                "risk_level": risk_map.get(verdict_label, "UNKNOWN"),
                "score": scoring["score"],
                "label": verdict_label,
                "breakdown": scoring["breakdown"],
                "modifiers": scoring["modifiers"],
                "hard_blocks": scoring["hard_blocks"],
            },
            "sea_distance_m": sea_dist,
            "property_tax": property_tax,
            "property_eligibility": property_eligibility,
            "opportunities": resolve_result.get("businesses", []),
            "intel_articles": intel_articles,
            "cache_hit": False,
        }

        # Cache result
        if self._cache:
            try:
                cache_data = {k: v for k, v in result.items() if k != "cache_hit"}
                await self._cache.set(cache_key, json.dumps(cache_data, default=str), ttl=14400)
            except (TypeError, ValueError) as exc:
                logger.debug("[PrimeNexus] Analyze cache serialize error: %s", exc)
            except Exception:
                logger.debug("[PrimeNexus] Analyze cache set failed")

        logger.info(
            "[PrimeNexus] analyze: verdict=%s score=%d zone=%s kbli=%s",
            verdict_label, scoring["score"], zone_code, kbli_code,
        )
        return result

    # ── Intel search (Qdrant balizero_news) ──────────────────────────
    async def _search_intel(
        self, zone_code: str, subdistrict: str, limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Semantic search for investment-relevant articles near the zone."""
        try:
            qdrant_url = os.environ.get("QDRANT_URL", "")
            qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")
            if not qdrant_url:
                return []

            from backend.core.embeddings import create_embeddings_generator

            query_text = f"Bali {subdistrict} zone {zone_code} investment regulation property news"
            embedder = create_embeddings_generator(api_key=os.environ.get("OPENAI_API_KEY"))
            embedding = await embedder.generate_single_embedding(query_text)

            search_url = f"{qdrant_url.rstrip('/')}/collections/balizero_news/points/search"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if qdrant_api_key:
                headers["api-key"] = qdrant_api_key

            client = await self._get_client()
            resp = await client.post(
                search_url,
                json={"vector": embedding, "limit": limit * 2, "with_payload": True},
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()

            articles: list[dict[str, Any]] = []
            for hit in data.get("result", []):
                score = hit.get("score", 0.0)
                if score < 0.45:
                    continue
                payload = hit.get("payload", {})
                title = payload.get("title", "")
                source_url = payload.get("source_url", "")
                if not title or not source_url:
                    continue
                articles.append({
                    "title": title,
                    "source_url": source_url,
                    "category": payload.get("category", ""),
                    "source_name": payload.get("source_name", ""),
                    "published_at": payload.get("published_at", ""),
                    "relevance_score": round(score, 3),
                })
                if len(articles) >= limit:
                    break
            return articles
        except httpx.HTTPError as exc:
            logger.debug("[PrimeNexus] Intel search HTTP error: %s", exc)
            return []
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.debug("[PrimeNexus] Intel search parse error: %s", exc)
            return []
        except Exception:
            logger.exception("[PrimeNexus] Intel search unexpected error")
            return []

    # ── Layer 3: CRM Intelligence Overlay ───────────────────────────
    async def intelligence(
        self,
        sw_lat: float, sw_lng: float,
        ne_lat: float, ne_lng: float,
        include_clients: bool = True,
        include_companies: bool = True,
        include_practices: bool = True,
        max_features: int = 2000,
    ) -> dict[str, Any]:
        """
        Query geocoded entities within a bounding box for CRM/INTEL overlay.
        Returns GeoJSON FeatureCollection with client/company/practice markers.
        Target: < 3s. Requires auth (called from CRM/INTEL modes).
        """
        features: list[dict[str, Any]] = []
        stats: dict[str, int] = {"clients": 0, "companies": 0, "practices": 0}

        pool = self._db_pool
        if not pool:
            # No pool injected — fallback to single connection (no leak)
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return {"type": "FeatureCollection", "features": [], "stats": stats}
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = await asyncpg.connect(db_url)
                try:
                    return await self._intelligence_query(conn, sw_lat, sw_lng, ne_lat, ne_lng,
                                                          include_clients, include_companies, max_features, features, stats)
                finally:
                    await conn.close()
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] Intelligence fallback failed: %s", exc)
                return {"type": "FeatureCollection", "features": [], "stats": stats}
            except Exception:
                logger.exception("[PrimeNexus] Intelligence fallback unexpected error")
                return {"type": "FeatureCollection", "features": [], "stats": stats}

        try:
            async with pool.acquire() as conn:
                return await self._intelligence_query(
                    conn, sw_lat, sw_lng, ne_lat, ne_lng,
                    include_clients, include_companies, max_features, features, stats,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("[PrimeNexus] Intelligence query failed: %s", exc)
        except Exception:
            logger.exception("[PrimeNexus] Intelligence query unexpected error")

        return {"type": "FeatureCollection", "features": [], "stats": stats}

    async def _intelligence_query(
        self,
        conn: asyncpg.Connection,
        sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
        include_clients: bool, include_companies: bool,
        max_features: int,
        features: list[dict[str, Any]], stats: dict[str, int],
    ) -> dict[str, Any]:
        """Execute intelligence queries against a connection."""
        if include_companies and len(features) < max_features:
            rows = await conn.fetch("""
                SELECT c.id, c.company_name, c.company_type, c.kbli_code,
                       c.status, c.rdtr_zone_code,
                       ST_Y(c.geo_point) as lat, ST_X(c.geo_point) as lng
                FROM companies c
                WHERE c.geo_point IS NOT NULL
                  AND ST_Contains(ST_MakeEnvelope($1, $2, $3, $4, 4326), c.geo_point)
                LIMIT $5
            """, sw_lng, sw_lat, ne_lng, ne_lat, max_features - len(features))
            for row in rows:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                    "properties": {
                        "entity_type": "company", "entity_id": row["id"],
                        "name": row["company_name"], "company_type": row["company_type"],
                        "kbli_code": row["kbli_code"], "status": row["status"],
                        "zone_code": row["rdtr_zone_code"],
                    },
                })
            stats["companies"] = len(rows)

        if include_clients and len(features) < max_features:
            rows = await conn.fetch("""
                SELECT c.id, c.full_name, c.status, c.nationality, c.rdtr_zone_code,
                       ST_Y(c.geo_point) as lat, ST_X(c.geo_point) as lng
                FROM clients c
                WHERE c.geo_point IS NOT NULL AND c.status = 'active'
                  AND ST_Contains(ST_MakeEnvelope($1, $2, $3, $4, 4326), c.geo_point)
                LIMIT $5
            """, sw_lng, sw_lat, ne_lng, ne_lat, max_features - len(features))
            for row in rows:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                    "properties": {
                        "entity_type": "client", "entity_id": row["id"],
                        "name": row["full_name"], "status": row["status"],
                        "nationality": row["nationality"], "zone_code": row["rdtr_zone_code"],
                    },
                })
            stats["clients"] = len(rows)

        return {"type": "FeatureCollection", "features": features[:max_features], "stats": stats}

    # ── Layer 4: Competitor Density ─────────────────────────────────

    # Saturation thresholds per zone-type prefix
    _SATURATION_THRESHOLDS: dict[str, int] = {
        "K": 100, "W": 50, "C": 80, "R": 20, "SPU": 60, "KT": 50,
    }

    # 2-digit KBLI sector labels
    _KBLI_2DIGIT_LABELS: dict[str, str] = {
        "10": "Food Manufacturing", "11": "Beverages", "41": "Construction",
        "46": "Wholesale Trade", "47": "Retail Trade", "49": "Transport",
        "55": "Accommodation", "56": "F&B Services", "58": "Publishing",
        "62": "Software/IT", "63": "Information Services", "68": "Real Estate",
        "70": "Management Consulting", "71": "Architecture/Engineering",
        "72": "Scientific R&D", "73": "Advertising/Marketing",
        "74": "Professional Services", "79": "Travel Agencies",
        "82": "Business Support", "85": "Education", "86": "Health Services",
        "90": "Creative/Arts", "93": "Sports/Recreation", "96": "Personal Services",
    }

    async def density(self, zone_code: str) -> dict[str, Any]:
        """Layer 4: Business density and competitor saturation for a zone."""
        cache_key = f"prime:density:{zone_code}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        by_kbli: dict[str, int] = {}
        total = 0

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT LEFT(kbli_code, 2) AS sector, COUNT(*) AS cnt
                        FROM companies
                        WHERE rdtr_zone_code = $1
                          AND kbli_code IS NOT NULL
                          AND kbli_code != ''
                        GROUP BY LEFT(kbli_code, 2)
                        ORDER BY cnt DESC
                        """,
                        zone_code,
                    )
                    for row in rows:
                        sector = row["sector"]
                        cnt = row["cnt"]
                        by_kbli[sector] = cnt
                        total += cnt
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] Density query failed: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Density query unexpected error")

        # Compute saturation index
        prefix = zone_code.split("-")[0] if "-" in zone_code else zone_code
        threshold = self._SATURATION_THRESHOLDS.get(prefix, 40)
        saturation = min(1.0, total / threshold) if threshold > 0 else 0.0
        saturation_label = "HIGH" if saturation > 0.7 else "MEDIUM" if saturation > 0.3 else "LOW"

        by_kbli_labels = {k: self._KBLI_2DIGIT_LABELS.get(k, f"Sector {k}") for k in by_kbli}

        result = {
            "zone_code": zone_code,
            "total_companies": total,
            "by_kbli": by_kbli,
            "by_kbli_labels": by_kbli_labels,
            "saturation_index": round(saturation, 2),
            "saturation_label": saturation_label,
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=21600)

        return result

    # ── Layer 5: Predictive Zone Score ─────────────────────────────

    async def predict_zone(self, zone_code: str) -> dict[str, Any]:
        """Layer 5: 3-signal trend analysis for a zone."""
        cache_key = f"prime:predict:{zone_code}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        factors: list[dict[str, Any]] = []
        trend_score = 0

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    # Signal 1: Rejection trend (6m vs prior 6m)
                    rej_rows = await conn.fetch(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE p.created_at >= NOW() - INTERVAL '6 months') AS recent,
                            COUNT(*) FILTER (WHERE p.created_at >= NOW() - INTERVAL '12 months'
                                             AND p.created_at < NOW() - INTERVAL '6 months') AS prior
                        FROM practices p
                        JOIN clients cl ON cl.id = p.client_id
                        WHERE cl.rdtr_zone_code = $1
                          AND p.status IN ('rejected', 'cancelled')
                        """,
                        zone_code,
                    )
                    if rej_rows:
                        recent_rej = rej_rows[0]["recent"] or 0
                        prior_rej = rej_rows[0]["prior"] or 0
                        if recent_rej > prior_rej + 2:
                            trend_score -= 1
                            factors.append({"signal": "rejections", "direction": "worse",
                                           "detail": f"{recent_rej} vs {prior_rej} prior period"})
                        elif recent_rej < prior_rej:
                            trend_score += 1
                            factors.append({"signal": "rejections", "direction": "better",
                                           "detail": f"{recent_rej} vs {prior_rej} prior period"})
                        else:
                            factors.append({"signal": "rejections", "direction": "stable",
                                           "detail": f"{recent_rej} recent, {prior_rej} prior"})

                    # Signal 2: Expiry density (practices expiring within 90 days)
                    exp_rows = await conn.fetch(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM practices p
                        JOIN clients cl ON cl.id = p.client_id
                        WHERE cl.rdtr_zone_code = $1
                          AND p.expiry_date IS NOT NULL
                          AND p.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '90 days'
                          AND p.status NOT IN ('completed', 'archived')
                        """,
                        zone_code,
                    )
                    expiring = exp_rows[0]["cnt"] if exp_rows else 0
                    if expiring > 5:
                        trend_score -= 1
                        factors.append({"signal": "expiring_practices", "direction": "worse",
                                       "detail": f"{expiring} expiring within 90 days"})
                    else:
                        factors.append({"signal": "expiring_practices", "direction": "stable",
                                       "detail": f"{expiring} expiring within 90 days"})

                    # Signal 3: Activity momentum (new companies 3m vs prior 3m)
                    act_rows = await conn.fetch(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '3 months') AS recent,
                            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '6 months'
                                             AND created_at < NOW() - INTERVAL '3 months') AS prior
                        FROM companies
                        WHERE rdtr_zone_code = $1
                        """,
                        zone_code,
                    )
                    if act_rows:
                        recent_act = act_rows[0]["recent"] or 0
                        prior_act = act_rows[0]["prior"] or 0
                        if recent_act > prior_act + 2:
                            trend_score += 1
                            factors.append({"signal": "new_companies", "direction": "better",
                                           "detail": f"{recent_act} vs {prior_act} prior period"})
                        elif recent_act < prior_act - 2:
                            trend_score -= 1
                            factors.append({"signal": "new_companies", "direction": "worse",
                                           "detail": f"{recent_act} vs {prior_act} prior period"})
                        else:
                            factors.append({"signal": "new_companies", "direction": "stable",
                                           "detail": f"{recent_act} recent, {prior_act} prior"})
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] Predict query failed: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Predict query unexpected error")

        trend = "improving" if trend_score >= 1 else "declining" if trend_score <= -1 else "stable"

        # Predict label shift
        current_label = "GREEN"  # default assumption
        predicted_label = current_label
        if trend == "declining":
            predicted_label = "YELLOW" if current_label == "GREEN" else "RED"
        elif trend == "improving":
            predicted_label = "GREEN" if current_label == "YELLOW" else current_label

        result = {
            "zone_code": zone_code,
            "trend": trend,
            "trend_score": trend_score,
            "predicted_label": predicted_label,
            "factors": factors,
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=43200)

        return result

    # ── Layer 6: Temporal Intelligence ──────────────────────────────

    _PERIOD_MAP: dict[str, str] = {
        "1m": "1 month", "3m": "3 months", "6m": "6 months", "12m": "12 months",
    }
    _GRANULARITY_MAP: dict[str, str] = {
        "daily": "day", "weekly": "week", "monthly": "month",
    }

    async def temporal(
        self, zone_code: str, period: str = "6m", granularity: str = "weekly",
    ) -> dict[str, Any]:
        """Layer 6: Temporal activity analysis for a zone."""
        cache_key = f"prime:temporal:{zone_code}:{period}:{granularity}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return {**json.loads(cached), "cache_hit": True}

        interval = self._PERIOD_MAP.get(period, "6 months")
        trunc = self._GRANULARITY_MAP.get(granularity, "week")
        buckets: list[dict[str, Any]] = []

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        f"""
                        WITH practice_buckets AS (
                            SELECT date_trunc('{trunc}', p.created_at) AS bucket,
                                   COUNT(*) AS practices
                            FROM practices p
                            JOIN clients cl ON cl.id = p.client_id
                            WHERE cl.rdtr_zone_code = $1
                              AND p.created_at >= NOW() - INTERVAL '{interval}'
                            GROUP BY bucket
                        ),
                        company_buckets AS (
                            SELECT date_trunc('{trunc}', created_at) AS bucket,
                                   COUNT(*) AS companies
                            FROM companies
                            WHERE rdtr_zone_code = $1
                              AND created_at >= NOW() - INTERVAL '{interval}'
                            GROUP BY bucket
                        )
                        SELECT COALESCE(p.bucket, c.bucket) AS bucket,
                               COALESCE(p.practices, 0) AS practices,
                               COALESCE(c.companies, 0) AS companies
                        FROM practice_buckets p
                        FULL OUTER JOIN company_buckets c ON p.bucket = c.bucket
                        ORDER BY bucket
                        """,
                        zone_code,
                    )
                    for row in rows:
                        practices = row["practices"]
                        companies = row["companies"]
                        buckets.append({
                            "date": row["bucket"].isoformat()[:10] if row["bucket"] else None,
                            "practices": practices,
                            "companies": companies,
                            "activity_score": practices + companies,
                        })
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] Temporal query failed: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Temporal query unexpected error")

        trend = "stable"
        if len(buckets) >= 2:
            mid = len(buckets) // 2
            first_half = sum(b["activity_score"] for b in buckets[:mid])
            second_half = sum(b["activity_score"] for b in buckets[mid:])
            if second_half > first_half * 1.3:
                trend = "increasing"
            elif second_half < first_half * 0.7:
                trend = "decreasing"

        result = {
            "zone_code": zone_code,
            "period": period,
            "granularity": granularity,
            "buckets": buckets,
            "trend": trend,
            "total_activity": sum(b["activity_score"] for b in buckets),
            "cache_hit": False,
        }

        if self._cache:
            await self._cache.set(cache_key, json.dumps(result, default=str), ttl=3600)

        return result

    # ── Layer 7: Live Regulation Feed ────────────────────────────────

    async def regulations(self, zone_code: str, limit: int = 10) -> dict[str, Any]:
        """Layer 7: Regulation feed for a zone from news_items + Qdrant."""
        regulations: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        zone_label = ZONE_LABELS.get(zone_code, {}).get("label_en", zone_code)

        # Source 1: SQL news_items
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, title, summary, category, ai_sentiment, published_at, source_url
                        FROM news_items
                        WHERE status = 'approved'
                          AND category IN ('immigration', 'business', 'tax', 'property', 'legal')
                          AND (
                            title ILIKE '%' || $1 || '%'
                            OR summary ILIKE '%' || $1 || '%'
                            OR title ILIKE '%' || $2 || '%'
                            OR summary ILIKE '%' || $2 || '%'
                          )
                        ORDER BY published_at DESC NULLS LAST
                        LIMIT $3
                        """,
                        zone_code, zone_label, limit,
                    )
                    for row in rows:
                        title = row["title"] or ""
                        norm = title.lower().strip()
                        if norm in seen_titles:
                            continue
                        seen_titles.add(norm)
                        regulations.append({
                            "title": title,
                            "summary": (row["summary"] or "")[:200],
                            "category": row["category"] or "",
                            "sentiment": row["ai_sentiment"] or "neutral",
                            "published_at": row["published_at"].isoformat() if row["published_at"] else "",
                            "source_url": row["source_url"] or "",
                            "source": "database",
                        })
            except (asyncpg.PostgresError, OSError) as exc:
                logger.warning("[PrimeNexus] Regulations SQL query failed: %s", exc)
            except Exception:
                logger.exception("[PrimeNexus] Regulations SQL unexpected error")

        # Source 2: Qdrant semantic search (reuse _search_intel)
        try:
            qdrant_articles = await self._search_intel(zone_code, zone_label, limit=limit)
            for art in qdrant_articles:
                norm = art.get("title", "").lower().strip()
                if norm in seen_titles:
                    continue
                seen_titles.add(norm)
                regulations.append({
                    "title": art.get("title", ""),
                    "summary": "",
                    "category": art.get("category", ""),
                    "sentiment": "neutral",
                    "published_at": art.get("published_at", ""),
                    "source_url": art.get("source_url", ""),
                    "source": "qdrant",
                })
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.debug("[PrimeNexus] Regulations Qdrant failed: %s", exc)
        except Exception:
            logger.exception("[PrimeNexus] Regulations Qdrant unexpected error")

        # Sort by published_at desc, cap at limit
        regulations.sort(key=lambda r: r.get("published_at", ""), reverse=True)
        regulations = regulations[:limit]

        return {
            "zone_code": zone_code,
            "regulations": regulations,
            "total_found": len(regulations),
        }

    # ── Layer 8: Proposals (Deal Flow) ─────────────────────────────

    async def create_proposal(
        self,
        lat: float,
        lng: float,
        zone_code: str,
        zone_name: str | None = None,
        kbli_code: str | None = None,
        verdict_label: str | None = None,
        verdict_score: int | None = None,
        analysis_snapshot: dict[str, Any] | None = None,
        investor_name: str | None = None,
        investor_email: str | None = None,
        investor_nationality: str | None = None,
    ) -> dict[str, Any]:
        """Create a shareable investment proposal."""
        import secrets
        token = secrets.token_urlsafe(32)

        if not self._db_pool:
            return {"error": "Database unavailable", "token": None}

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO prime_proposals (
                        token, lat, lng, zone_code, zone_name, kbli_code,
                        verdict_label, verdict_score, analysis_snapshot,
                        investor_name, investor_email, investor_nationality
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    RETURNING id, token, created_at, expires_at
                    """,
                    token, lat, lng, zone_code, zone_name, kbli_code,
                    verdict_label, verdict_score,
                    json.dumps(analysis_snapshot or {}, default=str),
                    investor_name, investor_email, investor_nationality,
                )
                return {
                    "id": row["id"],
                    "token": row["token"],
                    "created_at": row["created_at"].isoformat(),
                    "expires_at": row["expires_at"].isoformat(),
                    "status": "draft",
                }
        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("[PrimeNexus] Create proposal DB error: %s", exc)
            return {"error": str(exc), "token": None}
        except Exception as exc:
            logger.exception("[PrimeNexus] Create proposal unexpected error")
            return {"error": str(exc), "token": None}

    async def get_proposal(self, token: str) -> dict[str, Any] | None:
        """Retrieve a proposal by token (public access)."""
        if not self._db_pool:
            return None

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, token, lat, lng, zone_code, zone_name, kbli_code,
                           verdict_label, verdict_score, analysis_snapshot, pricing_snapshot,
                           investor_name, investor_email, investor_nationality,
                           status, created_at, expires_at, viewed_at
                    FROM prime_proposals
                    WHERE token = $1
                    """,
                    token,
                )
                if not row:
                    return None

                # Check expiry
                from datetime import datetime, timezone
                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return {"error": "expired", "expired_at": row["expires_at"].isoformat()}

                # Mark as viewed on first access
                if not row["viewed_at"]:
                    await conn.execute(
                        "UPDATE prime_proposals SET viewed_at = NOW(), status = 'viewed' WHERE id = $1",
                        row["id"],
                    )

                analysis = row["analysis_snapshot"]
                if isinstance(analysis, str):
                    analysis = json.loads(analysis)

                return {
                    "id": row["id"],
                    "token": row["token"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "zone_code": row["zone_code"],
                    "zone_name": row["zone_name"],
                    "kbli_code": row["kbli_code"],
                    "verdict_label": row["verdict_label"],
                    "verdict_score": row["verdict_score"],
                    "analysis": analysis,
                    "investor_name": row["investor_name"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                }
        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("[PrimeNexus] Get proposal DB error: %s", exc)
            return None
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("[PrimeNexus] Get proposal parse error: %s", exc)
            return None
        except Exception:
            logger.exception("[PrimeNexus] Get proposal unexpected error")
            return None

    # ── Layer 9: Portfolio Advisor ──────────────────────────────────

    async def portfolio(self, client_id: int) -> dict[str, Any]:
        """Layer 9: Aggregate portfolio view with health scoring and risk concentration."""
        entities: list[dict[str, Any]] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        if not self._db_pool:
            return {"client_id": client_id, "entities": [], "risk_concentration": {},
                    "suggestions": [], "overall_health": 0.0}

        try:
            async with self._db_pool.acquire() as conn:
                # Get companies for this client
                companies = await conn.fetch(
                    """
                    SELECT c.id, c.company_name, c.kbli_code, c.rdtr_zone_code,
                           ST_Y(c.geo_point::geometry) AS lat, ST_X(c.geo_point::geometry) AS lng,
                           c.status
                    FROM companies c
                    WHERE c.client_id = $1 AND c.geo_point IS NOT NULL
                    """,
                    client_id,
                )
                for comp in companies:
                    health = 1.0
                    issues: list[str] = []
                    zone = comp["rdtr_zone_code"]
                    if zone and zone in RESTRICTED_ZONES:
                        health -= 0.3
                        issues.append(f"Zone {zone} is restricted")
                    entities.append({
                        "type": "company", "id": comp["id"],
                        "name": comp["company_name"] or f"Company #{comp['id']}",
                        "zone_code": zone, "kbli_code": comp["kbli_code"],
                        "lat": comp["lat"], "lng": comp["lng"],
                        "status": comp["status"],
                        "health_score": round(max(0, health), 2),
                        "issues": issues,
                    })

                # Get practices with expiry
                practices = await conn.fetch(
                    """
                    SELECT p.id, p.practice_type_code, p.status, p.expiry_date,
                           p.notes
                    FROM practices p
                    WHERE p.client_id = $1 AND p.status NOT IN ('archived', 'completed')
                    ORDER BY p.expiry_date ASC NULLS LAST
                    LIMIT 20
                    """,
                    client_id,
                )
                for prac in practices:
                    days_until_expiry = None
                    health = 1.0
                    issues_p: list[str] = []
                    if prac["expiry_date"]:
                        from datetime import date
                        delta = prac["expiry_date"] - date.today()
                        days_until_expiry = delta.days
                        if days_until_expiry < 0:
                            health -= 0.5
                            issues_p.append("Expired")
                        elif days_until_expiry < 30:
                            health -= 0.3
                            issues_p.append(f"Expires in {days_until_expiry} days")
                            suggestions.append(f"Renew {prac['practice_type_code']} (expires in {days_until_expiry}d)")
                        elif days_until_expiry < 90:
                            health -= 0.1
                            issues_p.append(f"Expires in {days_until_expiry} days")
                    entities.append({
                        "type": "practice", "id": prac["id"],
                        "name": prac["practice_type_code"] or f"Practice #{prac['id']}",
                        "status": prac["status"],
                        "expiry_date": prac["expiry_date"].isoformat() if prac["expiry_date"] else None,
                        "days_until_expiry": days_until_expiry,
                        "health_score": round(max(0, health), 2),
                        "issues": issues_p,
                    })

        except (asyncpg.PostgresError, OSError) as exc:
            logger.warning("[PrimeNexus] Portfolio query failed: %s", exc)
        except Exception:
            logger.exception("[PrimeNexus] Portfolio query unexpected error")

        # Risk concentration
        from collections import Counter
        zone_counts = Counter(e.get("zone_code") for e in entities if e.get("zone_code"))
        kbli_counts = Counter(
            (e.get("kbli_code") or "")[:2] for e in entities
            if e.get("kbli_code") and e["type"] == "company"
        )

        zone_total = sum(zone_counts.values()) or 1
        zone_concentration = {z: round(c / zone_total, 2) for z, c in zone_counts.most_common(5)}
        kbli_total = sum(kbli_counts.values()) or 1
        kbli_concentration = {k: round(c / kbli_total, 2) for k, c in kbli_counts.most_common(5)}

        for zone, pct in zone_concentration.items():
            if pct > 0.8:
                warnings.append(f"{int(pct * 100)}% of companies in zone {zone} — consider diversifying")

        # Overall health
        health_scores = [e.get("health_score", 0.5) for e in entities]
        overall = round(sum(health_scores) / len(health_scores), 2) if health_scores else 0.0

        return {
            "client_id": client_id,
            "entities": entities,
            "risk_concentration": {
                "by_zone": zone_concentration,
                "by_kbli": kbli_concentration,
                "warnings": warnings,
            },
            "suggestions": suggestions,
            "overall_health": overall,
        }

    # ── Cache write ──────────────────────────────────────────────────
    async def _cache_zone(self, key: str, data: dict[str, Any]) -> None:
        if not self._cache:
            return
        try:
            cache_data = {k: v for k, v in data.items() if k != "cache_hit"}
            await self._cache.set(key, json.dumps(cache_data, default=str), ttl=86400)
        except (TypeError, ValueError) as exc:
            logger.debug("[PrimeNexus] Cache zone serialize error: %s", exc)
        except Exception as exc:
            logger.debug("[PrimeNexus] Cache zone set failed: %s", exc)
