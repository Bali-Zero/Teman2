"""
Integration Test Configuration

Sets up REAL database connections using testcontainers for PostgreSQL and Qdrant.
These tests verify service layer interactions with actual databases.
"""

import logging
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

# Set required environment variables BEFORE any imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Try to import testcontainers, but don't fail if not installed
try:
    from testcontainers.compose import DockerCompose
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False
    PostgresContainer = None
    DockerCompose = None
    RedisContainer = None


@pytest.fixture(scope="session")
def postgres_container():
    """
    Start PostgreSQL container for integration tests.

    Uses testcontainers if available, otherwise falls back to DATABASE_URL env var.
    """
    # Check if Docker is available
    import subprocess

    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
        docker_available = True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        docker_available = False

    if TESTCONTAINERS_AVAILABLE and docker_available:
        try:
            with PostgresContainer("postgres:15-alpine") as postgres:
                database_url = postgres.get_connection_url()
                os.environ["DATABASE_URL"] = database_url
                yield database_url
        except Exception as e:
            logger.warning(f"Docker container failed to start: {e}")
            # Fallback to DATABASE_URL env var
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                pytest.skip(f"Docker unavailable and DATABASE_URL not set: {e}")
            yield database_url
    else:
        # Fallback: use DATABASE_URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set and Docker/testcontainers not available")
        yield database_url


@pytest.fixture(scope="session")
def qdrant_container():
    """
    Start Qdrant container for integration tests.

    Uses docker-compose if available, otherwise falls back to QDRANT_URL env var.
    """
    qdrant_url = os.getenv("QDRANT_URL")

    if not qdrant_url:
        # Check if Docker is available
        import subprocess

        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
            docker_available = True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            docker_available = False

        # Try to use docker-compose for Qdrant
        if TESTCONTAINERS_AVAILABLE and docker_available:
            # Use docker-compose.test.yml if it exists
            compose_file = Path(__file__).parent.parent.parent / "docker-compose.test.yml"
            if compose_file.exists():
                try:
                    with DockerCompose(
                        str(compose_file.parent), compose_file_name="docker-compose.test.yml"
                    ) as compose:
                        # Wait for Qdrant to be ready (using port 6334 from docker-compose.test.yml)
                        import time

                        import requests

                        max_retries = 30
                        for i in range(max_retries):
                            try:
                                response = requests.get("http://localhost:6334/health", timeout=2)
                                if response.status_code == 200:
                                    break
                            except Exception:
                                if i < max_retries - 1:
                                    time.sleep(1)
                                else:
                                    raise

                        qdrant_url = "http://localhost:6334"
                        os.environ["QDRANT_URL"] = qdrant_url
                        yield qdrant_url
                        return
                except Exception as e:
                    logger.warning(f"Docker compose failed: {e}")
                    pytest.skip(f"QDRANT_URL not set and docker-compose failed: {e}")

        pytest.skip("QDRANT_URL not set and Docker/docker-compose not available")
    else:
        os.environ["QDRANT_URL"] = qdrant_url
        yield qdrant_url


@pytest_asyncio.fixture(scope="function")
async def db_pool(postgres_container):
    """
    Create asyncpg connection pool for PostgreSQL.
    Also creates necessary tables if they don't exist.

    Yields:
        asyncpg.Pool: Connection pool to test database
    """
    import asyncpg

    # Ensure we have a valid connection string
    # postgres_container should be a string URL (yielded from session fixture)
    database_url = postgres_container

    # Safety check: ensure we have a string, not a generator
    if not isinstance(database_url, str):
        # Fallback to environment variable
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not available and postgres_container is not a string")

    # Normalize URL (remove +psycopg2 if present, asyncpg doesn't support it)
    if database_url and "+" in database_url:
        database_url = database_url.replace("+psycopg2", "")

    # Create pool with proper error handling
    try:
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10, command_timeout=60)
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        pytest.skip(f"Database pool creation failed: {e}")

    # Create necessary tables if they don't exist
    async with pool.acquire() as conn:
        try:
            # Create memory_facts table (from migration 002_memory_system_schema.sql)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_facts (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    fact_type VARCHAR(50) DEFAULT 'profile_fact',
                    confidence FLOAT DEFAULT 1.0,
                    source VARCHAR(100) DEFAULT 'system',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            )

            # Create user_stats table (from migration 002_memory_system_schema.sql)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id VARCHAR(255) PRIMARY KEY,
                    conversations_count INTEGER DEFAULT 0,
                    searches_count INTEGER DEFAULT 0,
                    summary TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT NOW(),
                    last_activity TIMESTAMP DEFAULT NOW()
                )
            """
            )

            # Create index for faster lookups
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id)
            """
            )

            # Create CRM tables (from migration 007_crm_system_schema.sql)
            # Try to create UUID extension (may fail if not superuser, that's OK)
            try:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            except Exception:
                pass  # Extension might already exist or we don't have permissions

            # Create clients table - simplified version for tests
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        phone VARCHAR(50),
                        whatsapp VARCHAR(50),
                        status VARCHAR(50) DEFAULT 'active',
                        client_type VARCHAR(50) DEFAULT 'individual',
                        priority VARCHAR(50),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                """
                )
                logger.info("✅ Created clients table")
            except Exception as e:
                logger.error(f"❌ Could not create clients table: {e}")
                raise

            # Create practices table - simplified version for tests
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS practices (
                        id SERIAL PRIMARY KEY,
                        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                        practice_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        priority VARCHAR(50),
                        description TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255),
                        completed_at TIMESTAMP WITH TIME ZONE
                    )
                """
                )
                logger.info("✅ Created practices table")
            except Exception as e:
                logger.error(f"❌ Could not create practices table: {e}")
                raise

            # Create interactions table - simplified version for tests
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interactions (
                        id SERIAL PRIMARY KEY,
                        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                        practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
                        interaction_type VARCHAR(50) NOT NULL,
                        summary TEXT,
                        notes TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                """
                )
                logger.info("✅ Created interactions table")
            except Exception as e:
                logger.error(f"❌ Could not create interactions table: {e}")
                raise

            # Create other tables
            # Create conversations table - simplified
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        session_id VARCHAR(255),
                        rating INTEGER,
                        feedback TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                )
            except Exception as e:
                logger.warning(f"Could not create conversations table: {e}")

            # Create shared_memory table - simplified
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS shared_memory (
                        id SERIAL PRIMARY KEY,
                        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                        memory_type VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                """
                )
            except Exception as e:
                logger.warning(f"Could not create shared_memory table: {e}")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_queries (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    query TEXT NOT NULL,
                    response TEXT,
                    collection_used VARCHAR(100),
                    execution_time_ms FLOAT,
                    document_count INTEGER,
                    context_conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_feedback (
                    id SERIAL PRIMARY KEY,
                    query_id INTEGER REFERENCES oracle_queries(id) ON DELETE CASCADE,
                    user_id VARCHAR(255),
                    rating INTEGER,
                    feedback_text TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_activity (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    activity_type VARCHAR(50) NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    notes TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            # Create agent_executions table - simplified
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_executions (
                        id SERIAL PRIMARY KEY,
                        agent_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        completed_at TIMESTAMP WITH TIME ZONE,
                        result TEXT,
                        error TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                )
            except Exception as e:
                logger.warning(f"Could not create agent_executions table: {e}")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id SERIAL PRIMARY KEY,
                    task_name VARCHAR(255) UNIQUE NOT NULL,
                    task_type VARCHAR(100) NOT NULL,
                    enabled BOOLEAN DEFAULT true,
                    schedule VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    session_id VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255),
                    message TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    sent_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            # Create episodic_memories table (from migration 019)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(100) NOT NULL DEFAULT 'general',
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    emotion VARCHAR(50) DEFAULT 'neutral',
                    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    related_entities JSONB DEFAULT '[]',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodic_user_time ON episodic_memories(user_id, occurred_at DESC)"
            )

            # Create collective_memories table (from migration 018)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collective_memories (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    category VARCHAR(100),
                    confidence FLOAT DEFAULT 0.5,
                    source_count INTEGER DEFAULT 1,
                    is_promoted BOOLEAN DEFAULT FALSE,
                    first_learned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'
                )
            """
            )

            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_practices_client_id ON practices(client_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interactions_client_id ON interactions(client_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_activity_user_id ON team_activity(user_id)"
            )

            logger.info("✅ Created test database tables")

            # Verify tables were created
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('clients', 'practices', 'interactions', 'conversations')
            """
            )
            logger.info(f"✅ Verified tables exist: {[t['table_name'] for t in tables]}")
        except Exception as e:
            logger.error(f"❌ Could not create tables: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Don't raise - let tests fail naturally if tables don't exist

    yield pool

    # Clean up test data before closing pool
    try:
        async with pool.acquire() as conn:
            try:
                await conn.execute("DELETE FROM work_sessions WHERE user_id LIKE 'test_%'")
                await conn.execute(
                    "DELETE FROM clients WHERE email LIKE 'test_%' OR email LIKE '%@example.com'"
                )
                await conn.execute(
                    "DELETE FROM practices WHERE id IN (SELECT id FROM practices WHERE client_id IN (SELECT id FROM clients WHERE email LIKE '%@example.com'))"
                )
                await conn.execute(
                    "DELETE FROM interactions WHERE client_id IN (SELECT id FROM clients WHERE email LIKE '%@example.com')"
                )
            except Exception:
                pass  # Table might not exist
    except Exception:
        pass  # Pool might already be closed

    # Close pool after cleanup
    await pool.close()


@pytest.fixture(scope="function")
def qdrant_client(qdrant_container):
    """
    Create Qdrant client for integration tests.

    Yields:
        QdrantClient: Qdrant client connected to test instance
    """
    from core.qdrant_db import QdrantClient

    client = QdrantClient(qdrant_url=qdrant_container, collection_name="test_collection")

    yield client


@pytest_asyncio.fixture(scope="function")
async def memory_service(postgres_container):
    """
    Create MemoryServicePostgres with test database.
    Also creates necessary tables if they don't exist.

    Yields:
        MemoryServicePostgres: Memory service connected to test database
    """
    import asyncpg

    from services.memory_service_postgres import MemoryServicePostgres

    # Use database URL from postgres_container fixture
    # Normalize URL (remove +psycopg2 if present, asyncpg doesn't support it)
    database_url = postgres_container
    if database_url and "+" in database_url:
        database_url = database_url.replace("+psycopg2", "")

    # Create tables before creating service
    async with asyncpg.create_pool(database_url, min_size=1, max_size=1) as temp_pool:
        async with temp_pool.acquire() as conn:
            try:
                # Create memory_facts table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_facts (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        content TEXT NOT NULL,
                        fact_type VARCHAR(100) DEFAULT 'general',
                        confidence FLOAT DEFAULT 1.0,
                        source VARCHAR(50) DEFAULT 'user',
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                )

                # Create unique index for deduplication (case-insensitive)
                await conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_facts_unique
                    ON memory_facts(user_id, LOWER(content))
                """
                )

                # Create user_stats table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id VARCHAR(255) PRIMARY KEY,
                        conversations_count INTEGER DEFAULT 0,
                        searches_count INTEGER DEFAULT 0,
                        tasks_count INTEGER DEFAULT 0,
                        summary TEXT DEFAULT '',
                        preferences JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """
                )

                # Create indexes
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id)
                """
                )

                logger.info("✅ Created memory tables for test")
            except Exception as e:
                logger.warning(f"⚠️ Could not create tables (might already exist): {e}")

    service = MemoryServicePostgres(database_url=database_url)
    await service.connect()

    yield service

    await service.close()


@pytest.fixture(scope="function")
async def search_service(qdrant_client):
    """
    Create SearchService with test Qdrant instance.

    Yields:
        SearchService: Search service connected to test Qdrant
    """
    from services.search_service import SearchService

    # Override Qdrant URL in settings
    original_url = os.getenv("QDRANT_URL")
    os.environ["QDRANT_URL"] = qdrant_client.qdrant_url

    service = SearchService()

    yield service

    # Restore original URL
    if original_url:
        os.environ["QDRANT_URL"] = original_url
    elif "QDRANT_URL" in os.environ:
        del os.environ["QDRANT_URL"]


@pytest_asyncio.fixture(scope="function")
async def cleanup_postgres_data(postgres_container):
    """
    Clean up PostgreSQL test data before and after each test.

    This fixture is NOT autouse - only tests that need cleanup should request it.
    Note: db_pool might not be available for all tests, so we use postgres_container directly.
    """
    import asyncpg

    # Normalize URL (remove +psycopg2 if present)
    database_url = postgres_container
    if database_url and "+" in database_url:
        database_url = database_url.replace("+psycopg2", "")

    # Pre-test cleanup
    try:
        async with asyncpg.create_pool(database_url, min_size=1, max_size=1) as pool:
            async with pool.acquire() as conn:
                # Clean up test tables (handle missing tables gracefully)
                try:
                    await conn.execute("DELETE FROM user_memories WHERE user_id LIKE 'test_%'")
                except Exception:
                    pass  # Table might not exist
                try:
                    await conn.execute("DELETE FROM conversations WHERE user_id LIKE 'test_%'")
                except Exception:
                    pass  # Table might not exist
                try:
                    await conn.execute("DELETE FROM work_sessions WHERE user_id LIKE 'test_%'")
                except Exception:
                    pass  # Table might not exist
    except Exception:
        pass  # Database might not be available

    yield

    # Post-test cleanup
    try:
        async with asyncpg.create_pool(database_url, min_size=1, max_size=1) as pool:
            async with pool.acquire() as conn:
                try:
                    await conn.execute("DELETE FROM user_memories WHERE user_id LIKE 'test_%'")
                    await conn.execute("DELETE FROM conversations WHERE user_id LIKE 'test_%'")
                    await conn.execute("DELETE FROM work_sessions WHERE user_id LIKE 'test_%'")
                    await conn.execute(
                        "DELETE FROM clients WHERE email LIKE 'test_%' OR email LIKE '%@example.com'"
                    )
                    await conn.execute(
                        "DELETE FROM practices WHERE id IN (SELECT id FROM practices WHERE client_id IN (SELECT id FROM clients WHERE email LIKE '%@example.com'))"
                    )
                    await conn.execute(
                        "DELETE FROM interactions WHERE client_id IN (SELECT id FROM clients WHERE email LIKE '%@example.com')"
                    )
                except Exception:
                    pass
    except Exception:
        pass  # Database might not be available


@pytest.fixture(scope="function")
def cleanup_qdrant_data(qdrant_container):
    """
    Clean up Qdrant test collections before and after each test.

    This fixture is NOT autouse - only tests that need Qdrant should request it.
    """
    yield

    # Post-test cleanup: Clean up Qdrant test collections
    try:
        import requests

        requests.delete(f"{qdrant_container}/collections/test_collection", timeout=2)
    except Exception:
        pass  # Collection might not exist or Qdrant might not be available


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_websocket_connections():
    """
    Clean up WebSocket connections after each test.
    Ensures ConnectionManager is reset between tests.
    """
    yield

    # Post-test cleanup: Clear all WebSocket connections
    try:
        from app.routers.websocket import manager

        # Disconnect all active connections
        user_ids = list(manager.active_connections.keys())
        for user_id in user_ids:
            connections = manager.active_connections[user_id][:]
            for websocket in connections:
                try:
                    await manager.disconnect(websocket, user_id)
                except Exception:
                    pass  # Connection might already be closed

        # Clear the connections dict
        manager.active_connections.clear()
    except Exception:
        pass  # WebSocket manager might not be available


@pytest.fixture(scope="session")
def redis_container():
    """
    Start Redis container for integration tests.

    Uses testcontainers if available, otherwise falls back to REDIS_URL env var.
    """
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        # Check if Docker is available
        import subprocess

        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
            docker_available = True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            docker_available = False

        # Try to use docker-compose for Redis
        if TESTCONTAINERS_AVAILABLE and docker_available:
            # Use docker-compose.test.yml if it exists
            compose_file = Path(__file__).parent.parent.parent / "docker-compose.test.yml"
            if compose_file.exists():
                try:
                    with DockerCompose(
                        str(compose_file.parent), compose_file_name="docker-compose.test.yml"
                    ) as compose:
                        # Wait for Redis to be ready (using port 6380 from docker-compose.test.yml)
                        import time

                        import redis

                        max_retries = 30
                        redis_client = None
                        for i in range(max_retries):
                            try:
                                redis_client = redis.Redis(
                                    host="localhost", port=6380, decode_responses=True
                                )
                                redis_client.ping()
                                break
                            except Exception:
                                if i < max_retries - 1:
                                    time.sleep(1)
                                else:
                                    raise

                        redis_url = "redis://localhost:6380"
                        os.environ["REDIS_URL"] = redis_url
                        yield redis_url
                        return
                except Exception as e:
                    logger.warning(f"Docker compose failed for Redis: {e}")
                    # Try testcontainers RedisContainer as fallback
                    if TESTCONTAINERS_AVAILABLE and RedisContainer is not None:
                        try:
                            with RedisContainer("redis:7-alpine") as redis_container:
                                redis_url = redis_container.get_container_host_ip()
                                redis_port = redis_container.get_exposed_port(6379)
                                redis_url = f"redis://{redis_url}:{redis_port}"
                                os.environ["REDIS_URL"] = redis_url
                                yield redis_url
                                return
                        except Exception as e2:
                            logger.warning(f"RedisContainer failed: {e2}")
                    pytest.skip(f"REDIS_URL not set and docker-compose/RedisContainer failed: {e}")

        # Try testcontainers RedisContainer as fallback
        if TESTCONTAINERS_AVAILABLE and RedisContainer is not None:
            try:
                with RedisContainer("redis:7-alpine") as redis_container:
                    redis_url = redis_container.get_container_host_ip()
                    redis_port = redis_container.get_exposed_port(6379)
                    redis_url = f"redis://{redis_url}:{redis_port}"
                    os.environ["REDIS_URL"] = redis_url
                    yield redis_url
                    return
            except Exception as e:
                logger.warning(f"RedisContainer failed: {e}")

        pytest.skip("REDIS_URL not set and Docker/testcontainers not available")
    else:
        os.environ["REDIS_URL"] = redis_url
        yield redis_url


@pytest_asyncio.fixture(scope="function")
async def redis_client(redis_container):
    """
    Create Redis client for integration tests.

    Yields:
        redis.asyncio.Redis: Redis client connected to test instance
    """
    from redis.asyncio import Redis

    # Parse Redis URL
    redis_url = redis_container
    if not redis_url.startswith("redis://"):
        redis_url = f"redis://{redis_url}"

    client = Redis.from_url(redis_url, decode_responses=True)

    # Test connection
    try:
        await client.ping()
    except Exception as e:
        pytest.skip(f"Redis connection failed: {e}")

    yield client

    # Cleanup: Close connection
    await client.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_redis_connections(redis_container):
    """
    Clean up Redis connections after each test.
    Ensures Redis clients are properly closed and test data is cleared.
    """
    yield

    # Post-test cleanup: Clear test keys and close connections
    try:
        from redis.asyncio import Redis

        redis_url = redis_container
        if not redis_url.startswith("redis://"):
            redis_url = f"redis://{redis_url}"

        client = Redis.from_url(redis_url, decode_responses=True)
        try:
            # Clear test keys
            keys = await client.keys("test_*")
            keys.extend(await client.keys("semantic_cache:*"))
            keys.extend(await client.keys("embedding:*"))
            if keys:
                await client.delete(*keys)
        except Exception:
            pass  # Redis might not be available or keys might not exist
        finally:
            await client.close()
    except Exception:
        pass  # Redis might not be available
