import logging
from typing import Any

import asyncpg

# Utility per la costruzione sicura delle query
from backend.utils.query_builder import QueryBuilder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClientRepository:
    """
    Repository per l'accesso ai dati dei Clienti.
    Gestisce esclusivamente l'interazione con PostgreSQL tramite asyncpg,
    isolando la logica DB dal livello HTTP/Routing.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

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
                client_query = """
                    INSERT INTO clients (
                        full_name, email, phone, status, client_type,
                        whatsapp, nationality, passport_number,
                        assigned_to, avatar_url, address, notes,
                        tags, custom_fields, created_by,
                        lead_source, service_interest, tax_id,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14, $15,
                        $16, $17, $18,
                        NOW(), NOW()
                    )
                    RETURNING *
                """
                client_record = await conn.fetchrow(
                    client_query,
                    client_data.get("full_name"),
                    client_data.get("email"),
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
                    client_data.get("lead_source"),
                    client_data.get("service_interest", []),
                    client_data.get("tax_id"),
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
