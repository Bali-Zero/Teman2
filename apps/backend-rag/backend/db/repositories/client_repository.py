import logging
from datetime import date, datetime
from typing import Any

import asyncpg

from backend.db.base_repository import BaseRepository
from backend.services.common.cache import cache_invalidating
from backend.utils.query_builder import QueryBuilder

logger = logging.getLogger(__name__)


def _infer_lead_source(client_data: dict[str, Any]) -> str | None:
    """Infer CRM lead_source from explicit field or UTM params on landing_page.

    Priority:
      1. Explicit ``lead_source`` field (caller already classified)
      2. UTM medium ``whatsapp_cta`` OR utm_source ``whatsapp`` → ``whatsapp_inbound``
      3. ``landing_page`` present without UTM → ``website_organic``
      4. Otherwise None (caller must decide)

    Used by Plan A SEO Cell pre-natal Sprint 0 to differentiate web→WhatsApp
    leads from organic web→form leads. Migration 118 added the supporting
    ``referrer_url`` and ``landing_page`` columns.
    """
    if client_data.get("lead_source"):
        return client_data["lead_source"]

    landing = client_data.get("landing_page") or ""
    if "utm_medium=whatsapp_cta" in landing or "utm_source=whatsapp" in landing:
        return "whatsapp_inbound"
    if landing:
        return "website_organic"
    return None


def _normalize_email(value: str | None) -> str | None:
    """Normalize client email before storing it in the CRM table."""
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _parse_date(value: str | date | None) -> date | None:
    """Convert ISO date string to datetime.date for asyncpg DATE columns."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        # UU PDP audit: malformed date from upstream client payload. Returning
        # None is safe (column accepts NULL) but the original value must be
        # traceable for data-quality investigation.
        logger.debug(
            "client_repository.parse_date_failed",
            extra={"error_type": type(exc).__name__, "raw": str(value)[:32]},
        )
        return None


class ClientRepository(BaseRepository):
    """
    Repository per l'accesso ai dati dei Clienti.
    Gestisce esclusivamente l'interazione con PostgreSQL tramite asyncpg,
    isolando la logica DB dal livello HTTP/Routing.
    """

    async def search_clients_dynamic(
        self, filters: dict[str, Any], limit: int = 50, offset: int = 0,
    ) -> list[asyncpg.Record]:
        """
        1) USO DI QUERYBUILDER: Previene SQL Injection nelle ricerche dinamiche.
        Non concatena mai le stringhe manualmente.
        """
        try:
            # Inizializza il builder che gestirà la parametrizzazione sicura ($1, $2, ecc.)
            qb = QueryBuilder("SELECT * FROM clients")

            for field, value in filters.items():
                if value is not None:
                    # Il metodo where parametrizza automaticamente l'input contro le SQL injection
                    qb.where(f"{field} =", value)

            qb.limit(limit).offset(offset)
            query, params = qb.build()

            async with self.db_pool.acquire() as conn:
                return await conn.fetch(query, *params)

        except Exception as e:
            # 3) LOGGING STRUTTURATO: Nessun silent swallow
            logger.error(
                f"Errore imprevisto durante la ricerca dinamica dei clienti con filtri {filters}: {e}",
                exc_info=True,
            )
            raise

    @cache_invalidating([
        "zantara:crm_clients_stats:*",
        "zantara:crm_clients:*",
    ])
    async def create_client_with_details(
        self,
        client_data: dict[str, Any],
        company_data: dict[str, Any] | None = None,
        existing_company_id: int | None = None,
    ) -> asyncpg.Record:
        """
        2) ATOMICITÀ: Crea un cliente e, opzionalmente, la sua azienda associata.
        Avvolge l'intera operazione in un blocco transazionale esplicito.
        """
        async with self.db_pool.acquire() as conn, conn.transaction():
            # Garantisce che, se la creazione dell'azienda o del link fallisce,
            # anche il cliente venga rimosso, evitando dati orfani.
            try:
                # Inserimento del Cliente — tutti i campi dalla tabella clients
                # SEO attribution (migration 118): referrer_url, landing_page,
                # first_touch_at populated when present in payload. lead_source
                # inferred from UTM params on landing_page if caller did not set
                # it explicitly. See _infer_lead_source above.
                inferred_lead_source = _infer_lead_source(client_data)
                first_touch_at = client_data.get("first_touch_at")
                if first_touch_at and not isinstance(first_touch_at, datetime):
                    try:
                        first_touch_at = datetime.fromisoformat(str(first_touch_at))
                    except (ValueError, TypeError):
                        first_touch_at = None

                client_query = """
                    INSERT INTO clients (
                        full_name, email, phone, status, client_type,
                        whatsapp, nationality, passport_number,
                        assigned_to, avatar_url, address, notes,
                        tags, custom_fields, created_by,
                        lead_source, service_interest, tax_id,
                        passport_expiry, date_of_birth, company_name,
                        referrer_url, landing_page, first_touch_at,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14, $15,
                        $16, $17, $18,
                        $19, $20, $21,
                        $22, $23, $24,
                        NOW(), NOW()
                    )
                    RETURNING *
                """
                client_record = await conn.fetchrow(
                    client_query,
                    client_data.get("full_name"),
                    _normalize_email(client_data.get("email")),
                    client_data.get("phone"),
                    client_data.get("status", "active"),
                    client_data.get("client_type", "individual"),
                    client_data.get("whatsapp"),
                    client_data.get("nationality"),
                    client_data.get("passport_number"),
                    client_data.get("assigned_to"),
                    client_data.get("avatar_url"),
                    client_data.get("address"),
                    client_data.get("notes"),
                    client_data.get("tags", []),
                    client_data.get("custom_fields", {}),
                    client_data.get("created_by"),
                    inferred_lead_source,
                    client_data.get("service_interest", []),
                    client_data.get("tax_id"),
                    _parse_date(client_data.get("passport_expiry")),
                    _parse_date(client_data.get("date_of_birth")),
                    client_data.get("company_name"),
                    client_data.get("referrer_url"),
                    client_data.get("landing_page"),
                    first_touch_at,
                )

                # Inserimento opzionale della Compagnia e collegamento (Multi-tabella)
                # NIB-only dedup: if existing_company_id is set, skip INSERT and link directly
                company_id = None
                if existing_company_id and client_record:
                    company_id = existing_company_id
                    logger.info(
                        f"Linking client {client_record['id']} to existing company {company_id} (NIB dedup)"
                    )
                elif company_data and client_record:
                    nib = company_data.get("nib")
                    if nib:
                        company_query = """
                            INSERT INTO companies (company_name, kbli_code, nib, status, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, NOW(), NOW())
                            RETURNING id
                        """
                        company_record = await conn.fetchrow(
                            company_query,
                            company_data.get("company_name"),
                            company_data.get("kbli_code"),
                            nib,
                            company_data.get("status", "active"),
                        )
                    else:
                        company_query = """
                            INSERT INTO companies (company_name, kbli_code, status, created_at, updated_at)
                            VALUES ($1, $2, $3, NOW(), NOW())
                            RETURNING id
                        """
                        company_record = await conn.fetchrow(
                            company_query,
                            company_data.get("company_name"),
                            company_data.get("kbli_code"),
                            company_data.get("status", "active"),
                        )
                    company_id = company_record["id"]

                if company_id and client_record:
                    # Collegamento Client-Company
                    link_query = """
                        INSERT INTO client_company_links (client_id, company_id, role, is_primary)
                        VALUES ($1, $2, $3, $4)
                    """
                    role = company_data.get("role", "director") if company_data else "director"
                    is_primary = company_data.get("is_primary", True) if company_data else True
                    await conn.execute(
                        link_query,
                        client_record["id"],
                        company_id,
                        role,
                        is_primary,
                    )

                return client_record

            # 3) LOGGING STRUTTURATO PER ECCEZIONI SPECIFICHE
            except asyncpg.UniqueViolationError as e:
                logger.error(
                    f"Violazione constraint di unicità (es. email duplicata) per {client_data.get('email')}: {e}",
                    exc_info=True,
                )
                raise
            except asyncpg.ForeignKeyViolationError as e:
                logger.error(
                    f"Violazione Foreign Key durante la creazione cliente/compagnia: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"Fallimento critico e rollback nella transazione create_client_with_details: {e}",
                    exc_info=True,
                )
                raise
