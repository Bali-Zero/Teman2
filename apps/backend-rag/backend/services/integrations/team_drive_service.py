import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

# Import dei sottomoduli specializzati (risultato del refactoring del God Object)
from backend.services.integrations.drive.drive_auth import DriveAuthManager
from backend.services.integrations.drive.drive_operations import DriveOperationsManager
from backend.services.integrations.drive.drive_permissions import DrivePermissionsManager
from backend.services.integrations.drive.drive_audit import DriveAuditLogger

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TeamDriveService:
    """
    Facade Pattern per Team Drive.
    Fornisce accesso a Google Drive per i membri del team delegando 
    autenticazione, operazioni, permessi e audit ai rispettivi manager.
    
    Coordina i sottomoduli condividendo un singolo Connection Pool HTTPX
    per azzerare la latenza e prevenire memory leak.
    """

    def __init__(self, db_pool: Any):
        self.db_pool = db_pool
        
        # 1. Ottimizzazione HTTP: Client asincrono condiviso per reuse delle connessioni.
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        self.http_client = httpx.AsyncClient(limits=limits, timeout=30.0)
        
        # 2. Inizializzazione dei sottomoduli (Dependency Injection interna)
        self.audit = DriveAuditLogger()
        
        self.auth = DriveAuthManager(
            db_pool=self.db_pool, 
            http_client=self.http_client
        )
        
        self.operations = DriveOperationsManager(
            auth_manager=self.auth, 
            http_client=self.http_client, 
            audit=self.audit
        )
        
        self.permissions = DrivePermissionsManager(
            auth_manager=self.auth, 
            http_client=self.http_client, 
            audit=self.audit
        )

    async def close(self) -> None:
        """
        Garantisce la chiusura corretta del connection pool HTTPX.
        Deve essere chiamato in app.setup.service_initializer allo shutdown.
        """
        await self.http_client.aclose()
        logger.info("TeamDriveService HTTP client chiuso correttamente.")

    # =========================================================================
    # DELEGAZIONE METODI AUTH (Proxy/Facade)
    # =========================================================================

    async def get_access_token(self, user_id: str = "system") -> Optional[str]:
        return await self.auth.get_access_token(user_id)

    async def get_user_allowed_folders(self, user_email: str) -> Tuple[List[str], bool]:
        return await self.auth.get_user_allowed_folders(user_email)

    # =========================================================================
    # DELEGAZIONE METODI OPERATIONS (Proxy/Facade)
    # =========================================================================

    async def list_files(self, user_email: str, folder_id: Optional[str] = None, q: Optional[str] = None, page_size: int = 50, page_token: Optional[str] = None) -> Dict[str, Any]:
        return await self.operations.list_files(user_email=user_email, folder_id=folder_id, q=q, page_size=page_size, page_token=page_token)

    async def get_file_metadata(self, user_email: str, file_id: str) -> Dict[str, Any]:
        return await self.operations.get_file_metadata(user_email=user_email, file_id=file_id)

    async def download_file(self, user_email: str, file_id: str) -> Any:
        return await self.operations.download_file(user_email=user_email, file_id=file_id)

    async def get_folder_path(self, user_email: str, folder_id: str) -> List[Dict[str, Any]]:
        return await self.operations.get_folder_path(user_email=user_email, folder_id=folder_id)

    async def search_files(self, user_email: str, query: str, file_type: Optional[str] = None, page_size: int = 20) -> Dict[str, Any]:
        return await self.operations.search_files(user_email=user_email, query=query, file_type=file_type, page_size=page_size)

    async def upload_file(self, user_email: str, file: Any, parent_id: str) -> Dict[str, Any]:
        return await self.operations.upload_file(user_email=user_email, file=file, parent_id=parent_id)

    async def create_folder(self, user_email: str, request: Any) -> Dict[str, Any]:
        return await self.operations.create_folder(user_email=user_email, request=request)

    async def create_doc(self, user_email: str, request: Any) -> Dict[str, Any]:
        return await self.operations.create_doc(user_email=user_email, request=request)

    async def rename_file(self, user_email: str, file_id: str, request: Any) -> Dict[str, Any]:
        return await self.operations.rename_file(user_email=user_email, file_id=file_id, request=request)

    async def delete_file(self, user_email: str, file_id: str, permanent: bool = False) -> Dict[str, Any]:
        return await self.operations.delete_file(user_email=user_email, file_id=file_id, permanent=permanent)

    async def move_file(self, user_email: str, file_id: str, request: Any) -> Dict[str, Any]:
        return await self.operations.move_file(user_email=user_email, file_id=file_id, request=request)

    async def copy_file(self, user_email: str, file_id: str, request: Any) -> Dict[str, Any]:
        return await self.operations.copy_file(user_email=user_email, file_id=file_id, request=request)

    # =========================================================================
    # DELEGAZIONE METODI PERMISSIONS (Proxy/Facade)
    # =========================================================================

    async def list_permissions(self, user_email: str, file_id: str) -> List[Dict[str, Any]]:
        return await self.permissions.list_permissions(user_email=user_email, file_id=file_id)

    async def add_permission(self, user_email: str, file_id: str, request: Any) -> Dict[str, Any]:
        return await self.permissions.add_permission(user_email=user_email, file_id=file_id, request=request)

    async def update_permission(self, user_email: str, file_id: str, permission_id: str, request: Any) -> Dict[str, Any]:
        return await self.permissions.update_permission(user_email=user_email, file_id=file_id, permission_id=permission_id, request=request)

    async def remove_permission(self, user_email: str, file_id: str, permission_id: str) -> Dict[str, Any]:
        return await self.permissions.remove_permission(user_email=user_email, file_id=file_id, permission_id=permission_id)

def get_team_drive_service(db_pool: Any = None) -> TeamDriveService:
    """Helper compatibile con le vecchie dependencies FastAPI"""
    return TeamDriveService(db_pool)
