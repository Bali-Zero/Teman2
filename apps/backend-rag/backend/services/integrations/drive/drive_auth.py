import json
import logging
import os
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

# Metriche Prometheus (con fallback per sicurezza)
try:
    from backend.app.metrics import drive_oauth_refresh_total

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DriveAuthManager:
    """
    Gestisce l'autenticazione ibrida per Google Drive (OAuth + Service Account).
    Incorpora il rinnovo asincrono dei token OAuth e la validazione dei permessi (folder access rules).
    """

    def __init__(self, db_pool: asyncpg.Pool, http_client: httpx.AsyncClient) -> None:
        self.db_pool = db_pool
        self.http_client = http_client
        self.scopes = ["https://www.googleapis.com/auth/drive"]

    async def get_access_token(self, user_id: str = "system") -> str | None:
        """
        Recupera un token di accesso valido.
        Priorità 1: Token OAuth dal Database (es. sistema/admin).
        Priorità 2: Fallback su Service Account.
        """
        # 1. Tentativo di recupero tramite OAuth
        token = await self._get_or_refresh_oauth_token(user_id)
        if token:
            return token

        # 2. Fallback su Service Account in caso di fallimento OAuth
        logger.warning(f"OAuth token non disponibile per {user_id}. Fallback su Service Account.")
        return await self._get_service_account_token()

    async def _get_or_refresh_oauth_token(self, user_id: str) -> str | None:
        """
        Recupera il token OAuth da PostgreSQL. Se è scaduto o in scadenza (< 5 min),
        effettua il refresh asincrono tramite l'http_client condiviso.
        """
        try:
            async with self.db_pool.acquire() as conn:
                record = await conn.fetchrow(
                    """
                    SELECT access_token, refresh_token, expires_at
                    FROM google_drive_tokens
                    WHERE user_id = $1
                    """,
                    user_id,
                )

                if not record:
                    return None

                access_token = record["access_token"]
                refresh_token = record["refresh_token"]
                expires_at = record["expires_at"]

                # Assicura che expires_at sia aware della timezone per il calcolo
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                time_to_expiry = (expires_at - datetime.now(timezone.utc)).total_seconds()

                # Se mancano meno di 5 minuti alla scadenza, esegui il refresh
                if time_to_expiry < 300:
                    logger.info(
                        f"Token OAuth per {user_id} in scadenza (TTL: {time_to_expiry}s). Inizio refresh.",
                    )
                    return await self._refresh_oauth_token(user_id, refresh_token)

                return access_token

        except Exception as e:
            logger.error(
                f"Errore critico nel recupero token OAuth per {user_id}: {e}", exc_info=True,
            )
            return None

    async def _refresh_oauth_token(self, user_id: str, refresh_token: str) -> str | None:
        """
        Esegue la chiamata asincrona all'API di Google per ottenere un nuovo access_token,
        sfruttando il connection pool di HTTPX per azzerare i colli di bottiglia.
        """
        if not refresh_token:
            logger.error(
                f"Impossibile effettuare il refresh per {user_id}: refresh_token mancante.",
            )
            if METRICS_ENABLED:
                drive_oauth_refresh_total.labels(status="failed").inc()
            return None

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error(
                "Credenziali OAuth (Client ID/Secret) non configurate nelle variabili d'ambiente.",
            )
            return None

        try:
            # Esecuzione HTTP non bloccante
            response = await self.http_client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()

            new_access_token = data["access_token"]
            expires_in = data.get("expires_in", 3599)
            new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Aggiornamento atomico nel database
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE google_drive_tokens
                    SET access_token = $1, expires_at = $2, updated_at = NOW()
                    WHERE user_id = $3
                    """,
                    new_access_token,
                    new_expires_at,
                    user_id,
                )

            if METRICS_ENABLED:
                drive_oauth_refresh_total.labels(status="success").inc()

            logger.info(f"Refresh del token OAuth per {user_id} completato con successo.")
            return new_access_token

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Fallimento HTTP durante il refresh del token Google OAuth per {user_id}: {e.response.text}",
                exc_info=True,
            )
            if METRICS_ENABLED:
                drive_oauth_refresh_total.labels(status="failed").inc()
            return None
        except Exception as e:
            logger.error(
                f"Errore di sistema imprevisto durante il refresh token per {user_id}: {e}",
                exc_info=True,
            )
            if METRICS_ENABLED:
                drive_oauth_refresh_total.labels(status="failed").inc()
            return None

    async def _get_service_account_token(self) -> str | None:
        """
        Carica le credenziali del Service Account come fallback dalle variabili di ambiente.
        """
        try:
            sa_json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if not sa_json_str:
                logger.error(
                    "La variabile d'ambiente GOOGLE_SERVICE_ACCOUNT_JSON non è configurata.",
                )
                return None

            sa_info = json.loads(sa_json_str)
            credentials = service_account.Credentials.from_service_account_info(
                sa_info, scopes=self.scopes,
            )

            # Nota: L'oggetto request di google.auth è sincrono,
            # ma lo usiamo in fallback stretto per firmare e fare fetch del token
            request = GoogleAuthRequest()
            credentials.refresh(request)
            return credentials.token

        except json.JSONDecodeError as e:
            logger.error(
                f"GOOGLE_SERVICE_ACCOUNT_JSON contiene JSON non valido: {e}", exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(f"Errore caricamento del token Service Account: {e}", exc_info=True)
            return None

    async def get_user_allowed_folders(self, user_email: str) -> tuple[list[str], bool]:
        """
        Gestisce i permessi granulari dell'utente su base dipartimentale o esplicita.
        Verifica la tabella folder_access_rules per generare una whitelist di cartelle.
        Ritorna una tupla: (lista_cartelle_permesse, booleano_can_see_all)
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Interroga i permessi del dipartimento incrociando team_members, departments e folder_access_rules
                rows = await conn.fetch(
                    """
                    SELECT d.can_see_all, f.folder_name
                    FROM team_members tm
                    JOIN departments d ON tm.department = d.code
                    LEFT JOIN folder_access_rules f ON d.code = f.department_code
                    WHERE tm.email = $1 AND tm.active = true
                    """,
                    user_email,
                )

                if not rows:
                    return ([], False)

                # Se almeno un record segnala can_see_all come True (es. Owner/Founder)
                can_see_all = any(r.get("can_see_all", False) for r in rows)

                # Estrae i nomi dei folder specifici
                allowed_folders = [r["folder_name"] for r in rows if r["folder_name"] is not None]

                return (list(set(allowed_folders)), can_see_all)

        except Exception as e:
            logger.error(
                f"Fallimento recupero permessi folder per l'utente {user_email}: {e}", exc_info=True,
            )
            return ([], False)
