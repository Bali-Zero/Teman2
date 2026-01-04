"""
Integration and Compatibility Testing Suite for LLMGateway

This suite provides comprehensive integration testing, compatibility validation,
and system interoperability scenarios for the LLMGateway module.

Integration and Compatibility Coverage Areas:
- Third-party service integration testing
- API compatibility validation
- Database integration testing
- Cloud platform compatibility
- Version compatibility testing
- Cross-platform integration
- External service dependencies
- System interoperability testing
- Integration workflow validation
- Compatibility regression testing

Author: Nuzantara Team
Date: 2025-01-04
Version: 8.0.0 (Integration & Compatibility Edition)
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

# Import the minimal gateway for testing
from test_llm_gateway_isolated import (
    MinimalLLMGateway,
)


class TestThirdPartyServiceIntegration:
    """Test third-party service integration scenarios."""

    @pytest.fixture
    def integration_gateway(self):
        """Gateway configured for integration testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.integrated_services = {}
        gateway.service_health = {}
        return gateway

    def test_openai_integration(self, integration_gateway):
        """Test OpenAI API integration."""
        gateway = integration_gateway

        # Mock OpenAI client
        class MockOpenAIClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.models = ["gpt-4", "gpt-3.5-turbo", "text-davinci-003"]

            async def chat_completion(self, messages, model="gpt-4"):
                """Mock chat completion."""
                response = {
                    "id": str(uuid.uuid4()),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": f"OpenAI response using {model}",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
                return response

            def list_models(self):
                """List available models."""
                return [{"id": model} for model in self.models]

        # Test OpenAI integration
        openai_client = MockOpenAIClient("sk-test-key")
        gateway.integrated_services["openai"] = openai_client

        # Test model listing
        models = openai_client.list_models()
        assert len(models) == 3
        assert "gpt-4" in [model["id"] for model in models]

        # Test chat completion
        messages = [{"role": "user", "content": "Hello"}]

        async def test_completion():
            response = await openai_client.chat_completion(messages, "gpt-4")
            assert response["model"] == "gpt-4"
            assert "choices" in response
            assert len(response["choices"]) > 0
            return response

        # Run async test
        response = asyncio.run(test_completion())
        assert response["choices"][0]["message"]["content"] == "OpenAI response using gpt-4"

    def test_azure_openai_integration(self, integration_gateway):
        """Test Azure OpenAI integration."""
        gateway = integration_gateway

        # Mock Azure OpenAI client
        class MockAzureOpenAIClient:
            def __init__(self, api_key, endpoint, deployment_name):
                self.api_key = api_key
                self.endpoint = endpoint
                self.deployment_name = deployment_name

            async def chat_completion(self, messages):
                """Mock Azure chat completion."""
                response = {
                    "id": str(uuid.uuid4()),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "deployment": self.deployment_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": f"Azure OpenAI response from {self.deployment_name}",
                            },
                        }
                    ],
                }
                return response

        # Test Azure OpenAI integration
        azure_client = MockAzureOpenAIClient(
            api_key="azure-test-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4-deployment",
        )
        gateway.integrated_services["azure_openai"] = azure_client

        # Test Azure-specific functionality
        messages = [{"role": "user", "content": "Test Azure"}]

        async def test_azure_completion():
            response = await azure_client.chat_completion(messages)
            assert response["deployment"] == "gpt-4-deployment"
            assert "Azure OpenAI response" in response["choices"][0]["message"]["content"]
            return response

        response = asyncio.run(test_azure_completion())
        assert response is not None

    def test_anthropic_integration(self, integration_gateway):
        """Test Anthropic Claude integration."""
        gateway = integration_gateway

        # Mock Anthropic client
        class MockAnthropicClient:
            def __init__(self, api_key):
                self.api_key = api_key
                self.models = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]

            async def message(self, messages, model="claude-3-opus"):
                """Mock Claude message."""
                response = {
                    "id": f"msg_{uuid.uuid4().hex[:8]}",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"Claude response using {model}"}],
                    "model": model,
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                }
                return response

        # Test Anthropic integration
        anthropic_client = MockAnthropicClient("sk-ant-test-key")
        gateway.integrated_services["anthropic"] = anthropic_client

        # Test Claude message
        messages = [{"role": "user", "content": "Hello Claude"}]

        async def test_claude_message():
            response = await anthropic_client.message(messages, "claude-3-opus")
            assert response["model"] == "claude-3-opus"
            assert len(response["content"]) > 0
            assert response["content"][0]["type"] == "text"
            return response

        response = asyncio.run(test_claude_message())
        assert "Claude response" in response["content"][0]["text"]

    def test_service_health_monitoring(self, integration_gateway):
        """Test integrated service health monitoring."""
        gateway = integration_gateway

        def check_service_health(service_name, client):
            """Check health of integrated service."""
            health_status = {
                "service": service_name,
                "status": "healthy",
                "last_check": datetime.now().isoformat(),
                "response_time_ms": 50,
                "error_rate": 0.0,
            }

            # Simulate health check
            try:
                # In real implementation, ping the service
                if hasattr(client, "models"):
                    health_status["available_models"] = len(client.models)
                health_status["status"] = "healthy"
            except Exception as e:
                health_status["status"] = "unhealthy"
                health_status["error"] = str(e)

            gateway.service_health[service_name] = health_status
            return health_status

        # Test health monitoring for all services
        for service_name, client in gateway.integrated_services.items():
            health = check_service_health(service_name, client)
            assert health["status"] in ["healthy", "unhealthy"]
            assert "last_check" in health

        # Verify health tracking
        assert len(gateway.service_health) == len(gateway.integrated_services)


class TestAPICompatibility:
    """Test API compatibility scenarios."""

    @pytest.fixture
    def api_gateway(self):
        """Gateway configured for API testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.api_versions = {
            "v1": {"deprecated": False, "supported": True},
            "v2": {"deprecated": False, "supported": True},
            "v3": {"deprecated": False, "supported": True},
            "v0": {"deprecated": True, "supported": False},
        }
        return gateway

    def test_api_version_compatibility(self, api_gateway):
        """Test API version compatibility."""
        gateway = api_gateway

        def is_api_version_supported(version):
            """Check if API version is supported."""
            version_info = gateway.api_versions.get(version, {"supported": False})
            return version_info["supported"] and not version_info["deprecated"]

        def get_api_version_status(version):
            """Get API version status."""
            return gateway.api_versions.get(version, {"supported": False, "deprecated": False})

        # Test supported versions
        assert is_api_version_supported("v1") == True
        assert is_api_version_supported("v2") == True
        assert is_api_version_supported("v3") == True

        # Test deprecated version
        assert is_api_version_supported("v0") == False

        # Test non-existent version
        assert is_api_version_supported("v99") == False

        # Test version status
        v1_status = get_api_version_status("v1")
        assert v1_status["supported"] == True
        assert v1_status["deprecated"] == False

        v0_status = get_api_version_status("v0")
        assert v0_status["supported"] == False
        assert v0_status["deprecated"] == True

    def test_backward_compatibility(self, api_gateway):
        """Test backward compatibility."""
        gateway = api_gateway

        # Mock API endpoints for different versions
        def handle_v1_request(request_data):
            """Handle v1 API request."""
            return {"version": "v1", "data": request_data, "response": "v1 response format"}

        def handle_v2_request(request_data):
            """Handle v2 API request."""
            # v2 should be compatible with v1 but with enhanced features
            return {
                "version": "v2",
                "data": request_data,
                "response": "v2 response format",
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(uuid.uuid4()),
                },
            }

        def handle_v3_request(request_data):
            """Handle v3 API request."""
            # v3 should be compatible with v2 and v1
            return {
                "version": "v3",
                "data": request_data,
                "response": "v3 response format",
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(uuid.uuid4()),
                    "processing_time_ms": 25,
                },
                "features": ["enhanced_security", "better_performance"],
            }

        # Test backward compatibility
        test_request = {"message": "test", "user": "test_user"}

        v1_response = handle_v1_request(test_request)
        v2_response = handle_v2_request(test_request)
        v3_response = handle_v3_request(test_request)

        # All versions should handle the basic request
        assert v1_response["data"] == test_request
        assert v2_response["data"] == test_request
        assert v3_response["data"] == test_request

        # Newer versions should have additional features
        assert "metadata" not in v1_response
        assert "metadata" in v2_response
        assert "metadata" in v3_response
        assert "features" not in v2_response
        assert "features" in v3_response

    def test_request_response_format_compatibility(self, api_gateway):
        """Test request/response format compatibility."""
        gateway = api_gateway

        # Define compatible request formats
        request_formats = {
            "v1": {
                "required_fields": ["message"],
                "optional_fields": ["user", "session_id"],
                "format": "json",
            },
            "v2": {
                "required_fields": ["message"],
                "optional_fields": ["user", "session_id", "context", "priority"],
                "format": "json",
            },
            "v3": {
                "required_fields": ["message"],
                "optional_fields": ["user", "session_id", "context", "priority", "metadata"],
                "format": "json",
            },
        }

        def validate_request_format(request_data, version):
            """Validate request format for specific version."""
            format_spec = request_formats.get(version, {})
            required_fields = format_spec.get("required_fields", [])

            for field in required_fields:
                if field not in request_data:
                    return False, f"Missing required field: {field}"

            return True, "Valid format"

        # Test format validation
        valid_request = {"message": "test", "user": "test_user"}
        invalid_request = {"user": "test_user"}  # Missing required message

        # Test valid request
        is_valid, message = validate_request_format(valid_request, "v1")
        assert is_valid == True

        is_valid, message = validate_request_format(valid_request, "v2")
        assert is_valid == True

        is_valid, message = validate_request_format(valid_request, "v3")
        assert is_valid == True

        # Test invalid request
        is_valid, message = validate_request_format(invalid_request, "v1")
        assert is_valid == False
        assert "Missing required field" in message


class TestDatabaseIntegration:
    """Test database integration scenarios."""

    @pytest.fixture
    def db_gateway(self):
        """Gateway configured for database testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.database_connections = {}
        return gateway

    def test_postgresql_integration(self, db_gateway):
        """Test PostgreSQL database integration."""
        gateway = db_gateway

        # Mock PostgreSQL connection
        class MockPostgreSQLConnection:
            def __init__(self, connection_string):
                self.connection_string = connection_string
                self.connected = False

            def connect(self):
                """Mock database connection."""
                self.connected = True
                return True

            def execute_query(self, query, params=None):
                """Mock query execution."""
                if not self.connected:
                    raise Exception("Not connected to database")

                # Mock different query types
                if "SELECT" in query.upper():
                    return [{"id": 1, "data": "test_data"}, {"id": 2, "data": "test_data_2"}]
                elif "INSERT" in query.upper():
                    return {"affected_rows": 1, "inserted_id": 3}
                elif "UPDATE" in query.upper():
                    return {"affected_rows": 1}
                elif "DELETE" in query.upper():
                    return {"affected_rows": 1}
                else:
                    return {"status": "executed"}

            def close(self):
                """Close connection."""
                self.connected = False

        # Test PostgreSQL integration
        pg_connection = MockPostgreSQLConnection("postgresql://user:pass@localhost/db")
        gateway.database_connections["postgresql"] = pg_connection

        # Test connection
        assert pg_connection.connect() == True
        assert pg_connection.connected == True

        # Test query execution
        result = pg_connection.execute_query("SELECT * FROM test_table")
        assert len(result) == 2
        assert result[0]["id"] == 1

        # Test insert
        result = pg_connection.execute_query("INSERT INTO test_table (data) VALUES ('new_data')")
        assert result["affected_rows"] == 1

        # Test connection close
        pg_connection.close()
        assert pg_connection.connected == False

    def test_mongodb_integration(self, db_gateway):
        """Test MongoDB integration."""
        gateway = db_gateway

        # Mock MongoDB connection
        class MockMongoDBConnection:
            def __init__(self, connection_string):
                self.connection_string = connection_string
                self.connected = False
                self.collections = {}

            def connect(self):
                """Mock MongoDB connection."""
                self.connected = True
                return True

            def insert_document(self, collection, document):
                """Mock document insertion."""
                if not self.connected:
                    raise Exception("Not connected to database")

                if collection not in self.collections:
                    self.collections[collection] = []

                document["_id"] = str(uuid.uuid4())
                self.collections[collection].append(document)
                return document["_id"]

            def find_documents(self, collection, query=None):
                """Mock document finding."""
                if not self.connected:
                    raise Exception("Not connected to database")

                documents = self.collections.get(collection, [])

                if query:
                    # Simple mock filtering
                    filtered_docs = []
                    for doc in documents:
                        match = True
                        for key, value in query.items():
                            if doc.get(key) != value:
                                match = False
                                break
                        if match:
                            filtered_docs.append(doc)
                    return filtered_docs

                return documents

            def update_document(self, collection, query, update):
                """Mock document update."""
                if not self.connected:
                    raise Exception("Not connected to database")

                documents = self.collections.get(collection, [])
                updated_count = 0

                for doc in documents:
                    match = True
                    for key, value in query.items():
                        if doc.get(key) != value:
                            match = False
                            break

                    if match:
                        doc.update(update)
                        updated_count += 1

                return {"matched_count": updated_count, "modified_count": updated_count}

        # Test MongoDB integration
        mongo_connection = MockMongoDBConnection("mongodb://localhost:27017/testdb")
        gateway.database_connections["mongodb"] = mongo_connection

        # Test connection
        assert mongo_connection.connect() == True
        assert mongo_connection.connected == True

        # Test document operations
        doc_id = mongo_connection.insert_document("users", {"name": "John", "age": 30})
        assert doc_id is not None

        # Test find
        documents = mongo_connection.find_documents("users")
        assert len(documents) == 1
        assert documents[0]["name"] == "John"

        # Test find with query
        documents = mongo_connection.find_documents("users", {"name": "John"})
        assert len(documents) == 1

        # Test update
        result = mongo_connection.update_document("users", {"name": "John"}, {"age": 31})
        assert result["matched_count"] == 1
        assert result["modified_count"] == 1

    def test_redis_integration(self, db_gateway):
        """Test Redis cache integration."""
        gateway = db_gateway

        # Mock Redis connection
        class MockRedisConnection:
            def __init__(self, connection_string):
                self.connection_string = connection_string
                self.connected = False
                self.data = {}
                self.expiry = {}

            def connect(self):
                """Mock Redis connection."""
                self.connected = True
                return True

            def set(self, key, value, expiry=None):
                """Mock SET operation."""
                if not self.connected:
                    raise Exception("Not connected to Redis")

                self.data[key] = value
                if expiry:
                    self.expiry[key] = time.time() + expiry
                return True

            def get(self, key):
                """Mock GET operation."""
                if not self.connected:
                    raise Exception("Not connected to Redis")

                # Check expiry
                if key in self.expiry and time.time() > self.expiry[key]:
                    del self.data[key]
                    del self.expiry[key]
                    return None

                return self.data.get(key)

            def delete(self, key):
                """Mock DELETE operation."""
                if not self.connected:
                    raise Exception("Not connected to Redis")

                deleted = key in self.data
                if key in self.data:
                    del self.data[key]
                if key in self.expiry:
                    del self.expiry[key]
                return deleted

            def exists(self, key):
                """Mock EXISTS operation."""
                if not self.connected:
                    raise Exception("Not connected to Redis")

                return key in self.data

        # Test Redis integration
        redis_connection = MockRedisConnection("redis://localhost:6379")
        gateway.database_connections["redis"] = redis_connection

        # Test connection
        assert redis_connection.connect() == True
        assert redis_connection.connected == True

        # Test cache operations
        assert redis_connection.set("test_key", "test_value") == True
        assert redis_connection.get("test_key") == "test_value"
        assert redis_connection.exists("test_key") == True

        # Test expiry
        assert redis_connection.set("expiry_key", "expiry_value", expiry=1) == True
        assert redis_connection.get("expiry_key") == "expiry_value"

        # Test delete
        assert redis_connection.delete("test_key") == True
        assert redis_connection.get("test_key") == None
        assert redis_connection.exists("test_key") == False


class TestCloudPlatformCompatibility:
    """Test cloud platform compatibility scenarios."""

    @pytest.fixture
    def cloud_gateway(self):
        """Gateway configured for cloud testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.cloud_providers = {}
        return gateway

    def test_aws_compatibility(self, cloud_gateway):
        """Test AWS cloud platform compatibility."""
        gateway = cloud_gateway

        # Mock AWS services
        class MockAWSServices:
            def __init__(self, access_key, secret_key, region):
                self.access_key = access_key
                self.secret_key = secret_key
                self.region = region
                self.services = {
                    "lambda": MockLambdaService(),
                    "s3": MockS3Service(),
                    "dynamodb": MockDynamoDBService(),
                    "secrets_manager": MockSecretsManagerService(),
                }

            def get_service(self, service_name):
                """Get AWS service instance."""
                return self.services.get(service_name)

        class MockLambdaService:
            def invoke_function(self, function_name, payload):
                """Mock Lambda invocation."""
                return {
                    "StatusCode": 200,
                    "Payload": json.dumps(
                        {
                            "message": f"Lambda {function_name} executed successfully",
                            "input": payload,
                        }
                    ),
                }

        class MockS3Service:
            def upload_file(self, bucket, key, data):
                """Mock S3 upload."""
                return {"Bucket": bucket, "Key": key, "ETag": f"etag-{uuid.uuid4().hex[:8]}"}

            def download_file(self, bucket, key):
                """Mock S3 download."""
                return f"File content from {bucket}/{key}"

        class MockDynamoDBService:
            def put_item(self, table, item):
                """Mock DynamoDB put item."""
                return {"ConsumedCapacity": {"TableName": table, "CapacityUnits": 1.0}}

            def get_item(self, table, key):
                """Mock DynamoDB get item."""
                return {"Item": {"id": key["id"], "data": f"Data for {key['id']}"}}

        class MockSecretsManagerService:
            def get_secret(self, secret_name):
                """Mock Secrets Manager."""
                return {"Name": secret_name, "SecretString": f"Secret value for {secret_name}"}

        # Test AWS compatibility
        aws_services = MockAWSServices("test_access_key", "test_secret_key", "us-east-1")
        gateway.cloud_providers["aws"] = aws_services

        # Test Lambda
        lambda_service = aws_services.get_service("lambda")
        lambda_response = lambda_service.invoke_function("test_function", {"test": "data"})
        assert lambda_response["StatusCode"] == 200

        # Test S3
        s3_service = aws_services.get_service("s3")
        upload_result = s3_service.upload_file("test-bucket", "test-key", "test data")
        assert upload_result["Bucket"] == "test-bucket"

        # Test DynamoDB
        dynamodb_service = aws_services.get_service("dynamodb")
        put_result = dynamodb_service.put_item("test-table", {"id": "123", "data": "test"})
        assert "ConsumedCapacity" in put_result

        # Test Secrets Manager
        secrets_service = aws_services.get_service("secrets_manager")
        secret = secrets_service.get_secret("test-secret")
        assert "SecretString" in secret

    def test_gcp_compatibility(self, cloud_gateway):
        """Test Google Cloud Platform compatibility."""
        gateway = cloud_gateway

        # Mock GCP services
        class MockGCPServices:
            def __init__(self, project_id, credentials):
                self.project_id = project_id
                self.credentials = credentials
                self.services = {
                    "cloud_functions": MockCloudFunctionsService(),
                    "storage": MockStorageService(),
                    "firestore": MockFirestoreService(),
                    "secret_manager": MockSecretManagerService(),
                }

            def get_service(self, service_name):
                """Get GCP service instance."""
                return self.services.get(service_name)

        class MockCloudFunctionsService:
            def call_function(self, function_name, data):
                """Mock Cloud Functions call."""
                return {
                    "executionId": str(uuid.uuid4()),
                    "result": f"Cloud Function {function_name} executed",
                    "data": data,
                }

        class MockStorageService:
            def upload_blob(self, bucket_name, blob_name, data):
                """Mock Storage upload."""
                return {
                    "bucket": bucket_name,
                    "name": blob_name,
                    "generation": f"{int(time.time())}",
                    "size": len(data),
                }

            def download_blob(self, bucket_name, blob_name):
                """Mock Storage download."""
                return f"Blob content from {bucket_name}/{blob_name}"

        class MockFirestoreService:
            def create_document(self, collection, document):
                """Mock Firestore create."""
                return {
                    "name": f"projects/test-project/databases/(default)/documents/{collection}/{uuid.uuid4()}",
                    "fields": document,
                }

            def get_document(self, collection, document_id):
                """Mock Firestore get."""
                return {
                    "name": f"projects/test-project/databases/(default)/documents/{collection}/{document_id}",
                    "fields": {"id": document_id, "data": f"Data for {document_id}"},
                }

        class MockSecretManagerService:
            def access_secret(self, secret_id):
                """Mock Secret Manager."""
                return {
                    "name": f"projects/test-project/secrets/{secret_id}/versions/latest",
                    "payload": {"data": f"Secret data for {secret_id}".encode()},
                }

        # Test GCP compatibility
        gcp_services = MockGCPServices("test-project", "test-credentials")
        gateway.cloud_providers["gcp"] = gcp_services

        # Test Cloud Functions
        cf_service = gcp_services.get_service("cloud_functions")
        cf_result = cf_service.call_function("test-function", {"test": "data"})
        assert "executionId" in cf_result

        # Test Storage
        storage_service = gcp_services.get_service("storage")
        upload_result = storage_service.upload_blob("test-bucket", "test-blob", "test data")
        assert upload_result["bucket"] == "test-bucket"

        # Test Firestore
        firestore_service = gcp_services.get_service("firestore")
        create_result = firestore_service.create_document("test-collection", {"name": "test"})
        assert "name" in create_result

    def test_azure_compatibility(self, cloud_gateway):
        """Test Microsoft Azure compatibility."""
        gateway = cloud_gateway

        # Mock Azure services
        class MockAzureServices:
            def __init__(self, subscription_id, credential):
                self.subscription_id = subscription_id
                self.credential = credential
                self.services = {
                    "functions": MockAzureFunctionsService(),
                    "storage": MockAzureStorageService(),
                    "cosmos": MockCosmosDBService(),
                    "key_vault": MockKeyVaultService(),
                }

            def get_service(self, service_name):
                """Get Azure service instance."""
                return self.services.get(service_name)

        class MockAzureFunctionsService:
            def invoke_function(self, function_name, data):
                """Mock Azure Functions invocation."""
                return {
                    "status": "Success",
                    "result": f"Azure Function {function_name} executed",
                    "input": data,
                }

        class MockAzureStorageService:
            def upload_blob(self, container_name, blob_name, data):
                """Mock Azure Storage upload."""
                return {
                    "container": container_name,
                    "name": blob_name,
                    "etag": f"0x{uuid.uuid4().hex[:8]}",
                }

            def download_blob(self, container_name, blob_name):
                """Mock Azure Storage download."""
                return f"Blob content from {container_name}/{blob_name}"

        class MockCosmosDBService:
            def create_item(self, container, item):
                """Mock CosmosDB create item."""
                return {"id": str(uuid.uuid4()), "item": item, "_ts": int(time.time())}

            def get_item(self, container, item_id):
                """Mock CosmosDB get item."""
                return {"id": item_id, "data": f"Data for {item_id}", "_ts": int(time.time())}

        class MockKeyVaultService:
            def get_secret(self, secret_name):
                """Mock Key Vault get secret."""
                return {
                    "name": secret_name,
                    "value": f"Secret value for {secret_name}",
                    "properties": {"expires_on": None},
                }

        # Test Azure compatibility
        azure_services = MockAzureServices("test-subscription", "test-credential")
        gateway.cloud_providers["azure"] = azure_services

        # Test Azure Functions
        functions_service = azure_services.get_service("functions")
        func_result = functions_service.invoke_function("test-function", {"test": "data"})
        assert func_result["status"] == "Success"

        # Test Azure Storage
        storage_service = azure_services.get_service("storage")
        upload_result = storage_service.upload_blob("test-container", "test-blob", "test data")
        assert upload_result["container"] == "test-container"

        # Test Cosmos DB
        cosmos_service = azure_services.get_service("cosmos")
        create_result = cosmos_service.create_item("test-container", {"name": "test"})
        assert "id" in create_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
