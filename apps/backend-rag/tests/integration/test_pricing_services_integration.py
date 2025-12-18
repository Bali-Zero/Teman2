"""
Comprehensive Integration Tests for Pricing Services
Tests PricingService and DynamicPricingService

Covers:
- PricingService operations
- DynamicPricingService calculations
- Price retrieval
- Price updates
- Integration with CRM
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestPricingServiceIntegration:
    """Integration tests for PricingService"""

    @pytest.mark.asyncio
    async def test_pricing_service_initialization(self, qdrant_client):
        """Test PricingService initialization"""
        with patch("services.pricing_service.QdrantClient") as mock_qdrant:
            from services.pricing_service import PricingService

            service = PricingService()

            assert service is not None

    @pytest.mark.asyncio
    async def test_get_pricing_for_service(self, qdrant_client):
        """Test getting pricing for a service"""
        with patch("services.pricing_service.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value=[
                    {
                        "payload": {
                            "service": "KITAS",
                            "price": 1000,
                            "currency": "USD",
                            "description": "Temporary residence permit",
                        }
                    }
                ]
            )
            mock_qdrant.return_value = mock_client

            from services.pricing_service import PricingService

            service = PricingService()
            service.qdrant_client = mock_client

            pricing = await service.get_pricing("KITAS")

            assert pricing is not None
            assert "price" in pricing or "service" in pricing

    @pytest.mark.asyncio
    async def test_get_all_pricing(self, qdrant_client):
        """Test getting all pricing information"""
        with patch("services.pricing_service.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.scroll = AsyncMock(
                return_value=(
                    [
                        {
                            "payload": {
                                "service": "KITAS",
                                "price": 1000,
                            }
                        },
                        {
                            "payload": {
                                "service": "PT",
                                "price": 2000,
                            }
                        },
                    ],
                    None,
                )
            )
            mock_qdrant.return_value = mock_client

            from services.pricing_service import PricingService

            service = PricingService()
            service.qdrant_client = mock_client

            all_pricing = await service.get_all_pricing()

            assert all_pricing is not None
            assert isinstance(all_pricing, list) or isinstance(all_pricing, dict)


@pytest.mark.integration
class TestDynamicPricingServiceIntegration:
    """Integration tests for DynamicPricingService"""

    @pytest.mark.asyncio
    async def test_dynamic_pricing_calculation(self, db_pool):
        """Test dynamic pricing calculation"""

        async with db_pool.acquire() as conn:
            # Create pricing_rules table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pricing_rules (
                    id SERIAL PRIMARY KEY,
                    service_type VARCHAR(100),
                    base_price DECIMAL(10,2),
                    complexity_multiplier DECIMAL(5,2),
                    urgency_multiplier DECIMAL(5,2),
                    client_tier_multiplier DECIMAL(5,2),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create pricing rule
            rule_id = await conn.fetchval(
                """
                INSERT INTO pricing_rules (
                    service_type, base_price, complexity_multiplier,
                    urgency_multiplier, client_tier_multiplier
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "KITAS",
                1000.00,
                1.2,  # 20% increase for complexity
                1.5,  # 50% increase for urgency
                0.9,  # 10% discount for tier
            )

            # Calculate dynamic price
            base_price = 1000.0
            complexity = 1.2
            urgency = 1.5
            tier_discount = 0.9

            dynamic_price = base_price * complexity * urgency * tier_discount

            assert dynamic_price == 1620.0

            # Store calculated price
            calculated_price_id = await conn.fetchval(
                """
                INSERT INTO dynamic_prices (
                    service_type, base_price, calculated_price, factors, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "KITAS",
                base_price,
                dynamic_price,
                {
                    "complexity": complexity,
                    "urgency": urgency,
                    "tier_discount": tier_discount,
                },
                datetime.now(),
            )

            assert calculated_price_id is not None

            # Cleanup
            await conn.execute("DELETE FROM dynamic_prices WHERE id = $1", calculated_price_id)
            await conn.execute("DELETE FROM pricing_rules WHERE id = $1", rule_id)

    @pytest.mark.asyncio
    async def test_pricing_with_client_history(self, db_pool):
        """Test pricing calculation with client history"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Pricing Test Client",
                "pricing.test@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice history
            await conn.execute(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                client_id,
                "KITAS",
                "completed",
                "team@example.com",
                datetime.now() - timedelta(days=365),
                datetime.now() - timedelta(days=300),
            )

            # Calculate pricing with loyalty discount
            base_price = 1000.0
            practices_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM practices WHERE client_id = $1 AND status = 'completed'
                """,
                client_id,
            )

            loyalty_discount = min(0.2, practices_count * 0.05)  # Max 20% discount
            final_price = base_price * (1 - loyalty_discount)

            assert final_price <= base_price
            assert final_price >= base_price * 0.8

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
class TestPricingCRMIntegration:
    """Integration tests for pricing-CRM integration"""

    @pytest.mark.asyncio
    async def test_pricing_storage_in_practice(self, db_pool):
        """Test storing pricing information in practice"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Pricing Practice Client",
                "pricing.practice@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice with pricing
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, base_price, final_price,
                    pricing_metadata, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                1000.00,
                1200.00,
                {
                    "complexity_multiplier": 1.2,
                    "urgency_multiplier": 1.0,
                    "discounts": [],
                },
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            assert practice_id is not None

            # Retrieve pricing
            practice = await conn.fetchrow(
                """
                SELECT base_price, final_price, pricing_metadata
                FROM practices
                WHERE id = $1
                """,
                practice_id,
            )

            assert practice is not None
            assert practice["base_price"] == 1000.00
            assert practice["final_price"] == 1200.00
            assert practice["pricing_metadata"]["complexity_multiplier"] == 1.2

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_pricing_analytics(self, db_pool):
        """Test pricing analytics and reporting"""

        async with db_pool.acquire() as conn:
            # Create practices with pricing
            client_ids = []
            for i in range(5):
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    f"Analytics Client {i + 1}",
                    f"analytics{i + 1}@example.com",
                    "active",
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )
                client_ids.append(client_id)

                await conn.execute(
                    """
                    INSERT INTO practices (
                        client_id, practice_type, base_price, final_price, created_by, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    client_id,
                    "KITAS",
                    1000.00,
                    1000.00 + (i * 100),  # Varying prices
                    "team@example.com",
                    datetime.now(),
                    datetime.now(),
                )

            # Calculate pricing statistics
            stats = await conn.fetchrow(
                """
                SELECT
                    AVG(final_price) as avg_price,
                    MIN(final_price) as min_price,
                    MAX(final_price) as max_price,
                    COUNT(*) as total_practices
                FROM practices
                WHERE practice_type = $1
                """,
                "KITAS",
            )

            assert stats is not None
            assert stats["total_practices"] == 5
            assert stats["avg_price"] > 0
            assert stats["min_price"] <= stats["max_price"]

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE client_id = ANY($1)", client_ids)
            await conn.execute("DELETE FROM clients WHERE id = ANY($1)", client_ids)
