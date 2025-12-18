#!/usr/bin/env python3
"""
NUZANTARA PRIME - Module Template Generator
Creates a new module with complete structure following project standards.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ModuleGenerator:
    """Generates new module structure"""

    def __init__(self, module_name: str):
        self.module_name = module_name.lower()
        self.module_dir = backend_path / "app" / "modules" / self.module_name
        self.test_dir = backend_path.parent / "tests" / "modules" / self.module_name

    def generate_init_py(self) -> str:
        """Generate __init__.py"""
        return f'''"""
{self.module_name.title()} Module
"""

from .models import *
from .router import router
from .service import {self.module_name.title()}Service

__all__ = ["router", "{self.module_name.title()}Service"]
'''

    def generate_models_py(self) -> str:
        """Generate models.py with SQLModel"""
        return f'''"""
{self.module_name.title()} Models
SQLModel definitions for {self.module_name} module
"""

from typing import Optional
from datetime import datetime

from sqlmodel import Field, SQLModel


class {self.module_name.title()}Base(SQLModel):
    """Base model for {self.module_name}"""
    # TODO: Add fields
    name: str = Field(..., description="Name field")
    description: Optional[str] = Field(None, description="Description field")


class {self.module_name.title()}({self.module_name.title()}Base, table=True):
    """{self.module_name.title()} database model"""
    __tablename__ = "{self.module_name}s"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
'''

    def generate_service_py(self) -> str:
        """Generate service.py with business logic"""
        module = self.module_name
        Module = self.module_name.title()
        module_id_var = f"{module}_id"
        
        return f'''"""
{Module} Service
Business logic for {module} module
"""

import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class {Module}Service:
    """Service for {module} operations"""

    def __init__(self):
        """Initialize {Module}Service"""
        self.logger = logger

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new {module}
        
        Args:
            data: {module} data
            
        Returns:
            Created {module} data
            
        Raises:
            ValueError: If data is invalid
        """
        try:
            # TODO: Implement create logic
            self.logger.info("Creating {module}: %s", data)
            return {{"id": 1, **data}}
        except Exception as e:
            self.logger.error("Error creating {module}: %s", e, exc_info=True)
            raise

    async def get_by_id(self, {module_id_var}: int) -> Optional[dict[str, Any]]:
        """
        Get {module} by ID
        
        Args:
            {module_id_var}: {Module} ID
            
        Returns:
            {Module} data or None
        """
        try:
            # TODO: Implement get_by_id logic
            self.logger.info("Getting {module}: %s", {module_id_var})
            return None
        except Exception as e:
            self.logger.error("Error getting {module}: %s", e, exc_info=True)
            raise

    async def update(self, {module_id_var}: int, data: dict[str, Any]) -> dict[str, Any]:
        """
        Update {module}
        
        Args:
            {module_id_var}: {Module} ID
            data: Update data
            
        Returns:
            Updated {module} data
        """
        try:
            # TODO: Implement update logic
            self.logger.info("Updating {module}: %s", {module_id_var})
            return {{"id": {module_id_var}, **data}}
        except Exception as e:
            self.logger.error("Error updating {module}: %s", e, exc_info=True)
            raise

    async def delete(self, {module_id_var}: int) -> bool:
        """
        Delete {module}
        
        Args:
            {module_id_var}: {Module} ID
            
        Returns:
            True if deleted
        """
        try:
            # TODO: Implement delete logic
            self.logger.info("Deleting {module}: %s", {module_id_var})
            return True
        except Exception as e:
            self.logger.error("Error deleting {module}: %s", e, exc_info=True)
            raise
'''

    def generate_router_py(self) -> str:
        """Generate router.py with FastAPI endpoints"""
        module = self.module_name
        Module = self.module_name.title()
        module_id_var = f"{module}_id"
        route_param = f"{{{module_id_var}}}"
        
        template = '''"""
{Module} Router
API endpoints for {module} module
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .service import {Module}Service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/{module}", tags=["{Module}"])


def get_{module}_service(request: Request) -> {Module}Service:
    """Get {module} service from app state"""
    service = getattr(request.app.state, "{module}_service", None)
    if not service:
        service = {Module}Service()
        setattr(request.app.state, "{module}_service", service)
    return service


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_{module}(
    data: dict[str, Any],
    service: {Module}Service = Depends(get_{module}_service),
) -> dict[str, Any]:
    """
    Create a new {module}
    
    Args:
        data: {Module} data
        service: {Module}Service instance
        
    Returns:
        Created {module} data
    """
    try:
        result = await service.create(data)
        return {{"success": True, "data": result}}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Error creating {module}: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{route_param}")
async def get_{module}(
    {module_id_var}: int,
    service: {Module}Service = Depends(get_{module}_service),
) -> dict[str, Any]:
    """
    Get {module} by ID
    
    Args:
        {module_id_var}: {Module} ID
        service: {Module}Service instance
        
    Returns:
        {Module} data
    """
    try:
        result = await service.get_by_id({module_id_var})
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="{Module} not found",
            )
        return {{"success": True, "data": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting {module}: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{route_param}")
async def update_{module}(
    {module_id_var}: int,
    data: dict[str, Any],
    service: {Module}Service = Depends(get_{module}_service),
) -> dict[str, Any]:
    """
    Update {module}
    
    Args:
        {module_id_var}: {Module} ID
        data: Update data
        service: {Module}Service instance
        
    Returns:
        Updated {module} data
    """
    try:
        result = await service.update({module_id_var}, data)
        return {{"success": True, "data": result}}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Error updating {module}: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{route_param}")
async def delete_{module}(
    {module_id_var}: int,
    service: {Module}Service = Depends(get_{module}_service),
) -> dict[str, Any]:
    """
    Delete {module}
    
    Args:
        {module_id_var}: {Module} ID
        service: {Module}Service instance
        
    Returns:
        Deletion status
    """
    try:
        result = await service.delete({module_id_var})
        return {{"success": True, "deleted": result}}
    except Exception as e:
        logger.error("Error deleting {module}: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
'''
        
        return template.format(module=module, Module=Module, module_id_var=module_id_var, route_param=route_param)

    def generate_test_files(self) -> dict[str, str]:
        """Generate test files"""
        return {
            "test_models.py": f'''"""
Tests for {self.module_name} models
"""

import pytest
from .models import {self.module_name.title()}, {self.module_name.title()}Base


class Test{self.module_name.title()}Models:
    """Tests for {self.module_name.title()} models"""

    def test_{self.module_name}_base_creation(self):
        """Test {self.module_name.title()}Base creation"""
        data = {self.module_name.title()}Base(name="test")
        assert data.name == "test"

    def test_{self.module_name}_creation(self):
        """Test {self.module_name.title()} creation"""
        # TODO: Implement test
        pass
''',
            "test_service.py": f'''"""
Tests for {self.module_name} service
"""

from unittest.mock import AsyncMock, patch

import pytest

from ..{self.module_name}.service import {self.module_name.title()}Service


@pytest.fixture
def service():
    """Create {self.module_name.title()}Service instance"""
    return {self.module_name.title()}Service()


class Test{self.module_name.title()}Service:
    """Tests for {self.module_name.title()}Service"""

    @pytest.mark.asyncio
    async def test_create_success(self, service):
        """Test create success case"""
        # TODO: Implement test
        result = await service.create({{"name": "test"}})
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_error(self, service):
        """Test create error case"""
        # TODO: Implement test
        with pytest.raises(ValueError):
            await service.create({{}})

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, service):
        """Test get_by_id success case"""
        # TODO: Implement test
        result = await service.get_by_id(1)
        # assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, service):
        """Test get_by_id not found case"""
        # TODO: Implement test
        result = await service.get_by_id(999)
        assert result is None
''',
            "test_router.py": f'''"""
Tests for {self.module_name} router
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..{self.module_name}.router import router


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class Test{self.module_name.title()}Router:
    """Tests for {self.module_name.title()} router"""

    def test_create_{self.module_name}_success(self, client, app):
        """Test create {self.module_name} success"""
        with patch("app.modules.{self.module_name}.router.get_{self.module_name}_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.create = AsyncMock(return_value={{"id": 1, "name": "test"}})
            mock_get.return_value = mock_service

            response = client.post("/api/{self.module_name}/", json={{"name": "test"}})
            assert response.status_code == 201
            assert response.json()["success"] is True

    def test_create_{self.module_name}_error(self, client, app):
        """Test create {self.module_name} error"""
        with patch("app.modules.{self.module_name}.router.get_{self.module_name}_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.create = AsyncMock(side_effect=ValueError("Invalid data"))
            mock_get.return_value = mock_service

            response = client.post("/api/{self.module_name}/", json={{}})
            assert response.status_code == 400

    def test_get_{self.module_name}_success(self, client, app):
        """Test get {self.module_name} success"""
        with patch("app.modules.{self.module_name}.router.get_{self.module_name}_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.get_by_id = AsyncMock(return_value={{"id": 1, "name": "test"}})
            mock_get.return_value = mock_service

            response = client.get("/api/{self.module_name}/1")
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_get_{self.module_name}_not_found(self, client, app):
        """Test get {self.module_name} not found"""
        with patch("app.modules.{self.module_name}.router.get_{self.module_name}_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.get_by_id = AsyncMock(return_value=None)
            mock_get.return_value = mock_service

            response = client.get("/api/{self.module_name}/999")
            assert response.status_code == 404
'''
        }

    def generate(self) -> None:
        """Generate complete module structure"""
        # Create directories
        self.module_dir.mkdir(parents=True, exist_ok=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Generate module files
        (self.module_dir / "__init__.py").write_text(self.generate_init_py())
        (self.module_dir / "models.py").write_text(self.generate_models_py())
        (self.module_dir / "service.py").write_text(self.generate_service_py())
        (self.module_dir / "router.py").write_text(self.generate_router_py())

        # Generate test files
        test_files = self.generate_test_files()
        for filename, content in test_files.items():
            (self.test_dir / filename).write_text(content)

        logger.info(f"✅ Module '{self.module_name}' created successfully!")
        logger.info(f"   Module directory: {self.module_dir}")
        logger.info(f"   Test directory: {self.test_dir}")
        logger.info("\n📝 Next steps:")
        logger.info("   1. Review and customize models.py")
        logger.info("   2. Implement service methods")
        logger.info("   3. Complete test implementations")
        logger.info("   4. Register router in main_cloud.py")
        logger.info("   5. Run tests: pytest tests/modules/{}/".format(self.module_name))


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Create a new module with complete structure")
    parser.add_argument("module_name", type=str, help="Name of the module to create")

    args = parser.parse_args()

    generator = ModuleGenerator(args.module_name)
    generator.generate()


if __name__ == "__main__":
    main()

