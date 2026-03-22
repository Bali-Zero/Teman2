import logging
from typing import Any, Dict, List, Optional
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

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def search_clients_dynamic(
        self, 
        filters: Dict[str, Any], 
        limit: int = 50, 
        offset: int = 0
    ) -> List[asyncpg.Record]:
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
            logger.error(f"Errore imprevisto durante la ricerca dinamica dei clienti con filtri {filters}: {e}", exc_info=True)
            raise

    async def create_client_with_details(
        self, 
        client_data: Dict[str, Any], 
        company_data: Optional[Dict[str, Any]] = None
    ) -> asyncpg.Record:
        """
        2) ATOMICITÀ: Crea un cliente e, opzionalmente, la sua azienda associata.
        Avvolge l'intera operazione in un blocco transazionale esplicito.
        """
        async with self.db_pool.acquire() as conn:
            # Garantisce che, se la creazione dell'azienda o del link fallisce, 
            # anche il cliente venga rimosso, evitando dati orfani.
            async with conn.transaction():
                try:
                    # Inserimento del Cliente
                    client_query = """
                        INSERT INTO clients (full_name, email, phone, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        RETURNING *
                    """
                    client_record = await conn.fetchrow(
                        client_query,
                        client_data.get("full_name"),
                        client_data.get("email"),
                        client_data.get("phone"),
                        client_data.get("status", "active")
                    )

                    # Inserimento opzionale della Compagnia e collegamento (Multi-tabella)
                    if company_data and client_record:
                        company_query = """
                            INSERT INTO companies (company_name, kbli_code, status, created_at, updated_at)
                            VALUES ($1, $2, $3, NOW(), NOW())
                            RETURNING id
                        """
                        company_record = await conn.fetchrow(
                            company_query,
                            company_data.get("company_name"),
                            company_data.get("kbli_code"),
                            company_data.get("status", "active")
                        )

                        # Collegamento Client-Company
                        link_query = """
                            INSERT INTO client_company_links (client_id, company_id, role, is_primary)
                            VALUES ($1, $2, $3, $4)
                        """
                        await conn.execute(
                            link_query,
                            client_record["id"],
                            company_record["id"],
                            company_data.get("role", "director"),
                            company_data.get("is_primary", True)
                        )

                    return client_record

                # 3) LOGGING STRUTTURATO PER ECCEZIONI SPECIFICHE
                except asyncpg.UniqueViolationError as e:
                    logger.error(
                        f"Violazione constraint di unicità (es. email duplicata) per {client_data.get('email')}: {e}", 
                        exc_info=True
                    )
                    raise
                except asyncpg.ForeignKeyViolationError as e:
                    logger.error(
                        f"Violazione Foreign Key durante la creazione cliente/compagnia: {e}", 
                        exc_info=True
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f"Fallimento critico e rollback nella transazione create_client_with_details: {e}", 
                        exc_info=True
                    )
                    raise
