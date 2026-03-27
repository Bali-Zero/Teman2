import logging
from typing import Any

import asyncpg

# Eccezioni custom di Dominio
from backend.app.core.exceptions import ResourceConflictError

# Interfaccia Repository (Type Hinting)
from backend.db.repositories.client_repository import ClientRepository
from backend.services.crm.cache_manager import invalidate_client_cache

# Validazione e Caching
from backend.services.crm.validators import ClientValidator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClientService:
    """
    Servizio per la gestione della logica di business dei Clienti CRM.
    Agisce come intermediario tra il livello API (Router) e l'accesso ai dati (Repository),
    garantendo validazione, gestione della cache e mappatura sicura degli errori.
    """

    def __init__(self, repository: ClientRepository) -> None:
        self.repository = repository

    async def create_client(
        self, client_data: dict[str, Any], company_data: dict[str, Any] | None = None
    ) -> asyncpg.Record:
        """
        1. Valida l'input tramite Pydantic
        2. Persiste i dati tramite Repository (transazionale)
        3. Invalida la cache pertinente
        4. Mappa le eccezioni DB in eccezioni di dominio (Clean Architecture)
        """
        try:
            # 1. Validazione rigorosa dell'input
            # Utilizza il ClientValidator per sanificare campi, formati e dati obbligatori
            validated_data = ClientValidator(**client_data).model_dump(exclude_unset=True)

            # 2. Esecuzione tramite Repository (garantisce atomicità se c'è company_data)
            created_record = await self.repository.create_client_with_details(
                client_data=validated_data, company_data=company_data
            )

            # 3. Invalidazione della Cache
            # Rimuove le chiavi stale per il client appena creato per mantenere consistenza
            client_id = created_record["id"]
            invalidate_client_cache(client_id)

            logger.info(f"Cliente creato con successo nel Service Layer: ID {client_id}")
            return created_record

        except asyncpg.UniqueViolationError as e:
            # 4. Mappatura eccezioni ("Silent Swallows" replacement)
            # Trasforma l'errore DB in un'eccezione custom riconosciuta dall'applicativo
            logger.error(
                f"Conflitto di risorse: email o numero di telefono già presenti. Dettagli: {e}",
                exc_info=True,
            )
            raise ResourceConflictError(
                "Un cliente con questi dati unici (es. email o telefono) esiste già."
            ) from e

        except Exception as e:
            # Propaga altri errori critici mantenendo la traccia nei log
            logger.error(
                f"Errore imprevisto nella logica di business di create_client: {e}", exc_info=True
            )
            raise
