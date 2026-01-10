# 🚧 Technical Debt Board - 2026-01-10

## 📊 Summary

| Metric | Count |
|--------|-------|
| Total Items | 37 |
| P0 (Critical) | 0 |
| P1 (High) | 1 |
| P2 (Medium) | 0 |
| P3 (Low) | 36 |

### By Type
- TODO: 36
- FIXME: 0
- HACK: 0
- BUG: 1

### By Component
- backend: 16
- frontend: 10
- scraper: 1
- shared: 10

---

## 🚨 P0 - Critical Issues

✅ No critical issues found!

---

## ⚠️ P1 - High Priority

### BUG - P1

**File:** `apps/backend-rag/tests/unit/routers/test_ingest_router.py:483`

**Component:** backend

**Content:**
```
# BUG: Returns 500 due to validation error (tier="Unknown")
            assert response.status_code == 500
            assert "validation error" in response.json()["detail"].lower()

    def test_batch_ingest_directory_not_found(self, client):
        """Test batch ingestion when directory doesn't exist"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            mock_path_class.return_value = mock_dir

            request_data = {"directory_path": "/nonexistent/path"}

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 404
            assert "Directory not found" in response.json()["detail"]

    def test_batch_ingest_no_books_found(self, client):
        """Test batch ingestion when no matching books found"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_dir.glob.return_value = []  # No files
            mock_path_class.return_value = mock_dir

            request_data = {"directory_path": "/data/empty"}

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 400
            assert "No books found" in response.json()["detail"]

    def test_batch_ingest_default_patterns(self, client, mock_ingestion_service):
        """Test batch ingestion with default file patterns"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_path_class.return_value = mock_dir

            mock_file = MagicMock()
            mock_file.stem = "test_book"

            # Should be called twice (for *.pdf and *.epub)
            mock_dir.glob.side_effect = [[mock_file], []]

            mock_ingestion_service.ingest_book.return_value = {
                "success": True,
                "book_title": "Test",
                "book_author": "Author",
                "tier": "A",
                "chunks_created": 50,
                "message": "Success",
                "error": None,
            }

            # Don't specify file_patterns - should use defaults
            request_data = {"directory_path": "/data/books"}

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 200
            # Verify both patterns were used
            assert mock_dir.glob.call_count == 2

    def test_batch_ingest_custom_patterns(self, client, mock_ingestion_service):
        """Test batch ingestion with custom file patterns"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_path_class.return_value = mock_dir

            mock_file = MagicMock()
            mock_file.stem = "test"
            mock_dir.glob.return_value = [mock_file]

            mock_ingestion_service.ingest_book.return_value = {
                "success": True,
                "book_title": "Test",
                "book_author": "Author",
                "tier": "A",
                "chunks_created": 50,
                "message": "Success",
                "error": None,
            }

            request_data = {
                "directory_path": "/data/books",
                "file_patterns": ["*.txt", "*.md"],
            }

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 200

    def test_batch_ingest_all_failures(self, client, mock_ingestion_service):
        """
        Test batch ingestion when all books fail

        NOTE: Due to tier="Unknown" validation bug, returns 500
        """
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_path_class.return_value = mock_dir

            mock_file1 = MagicMock()
            mock_file1.stem = "book1"
            mock_file2 = MagicMock()
            mock_file2.stem = "book2"
            mock_dir.glob.return_value = [mock_file1, mock_file2]

            # All fail
            mock_ingestion_service.ingest_book.side_effect = [
                Exception("Error 1"),
                Exception("Error 2"),
            ]

            request_data = {"directory_path": "/data/books"}

            response = client.post("/api/ingest/batch", json=request_data)

            # BUG: Returns 500 due to tier validation
            assert response.status_code == 500
            assert "validation error" in response.json()["detail"].lower()

    def test_batch_ingest_service_reports_failure(self, client, mock_ingestion_service):
        """
        Test batch when service returns success=False

        Uses valid tier to avoid validation error
        """
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_path_class.return_value = mock_dir

            mock_file = MagicMock()
            mock_file.stem = "book"
            # Return file for first pattern, empty for second
            mock_dir.glob.side_effect = [[mock_file], []]

            # Service reports failure in response - use valid tier
            mock_ingestion_service.ingest_book.return_value = {
                "success": False,
                "book_title": "Failed Book",
                "book_author": "Author",
                "tier": "D",  # Use valid tier instead of "Unknown"
                "chunks_created": 0,
                "message": "Validation failed",
                "error": "Invalid format",
            }

            request_data = {"directory_path": "/data/books"}

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 200
            result = response.json()
            assert result["successful"] == 0
            assert result["failed"] == 1

    def test_batch_ingest_unexpected_exception(self, client):
        """Test batch ingestion with unexpected exception"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_path_class.side_effect = Exception("Unexpected error")

            request_data = {"directory_path": "/data/books"}

            response = client.post("/api/ingest/batch", json=request_data)

            assert response.status_code == 500
            assert "Batch ingestion failed" in response.json()["detail"]


# ============================================================================
# STATS ENDPOINT TESTS
# ============================================================================


class TestStatsEndpoint:
    """Tests for GET /api/ingest/stats"""

    def test_get_stats_success(self, client, mock_qdrant_client):
        """Test successful stats retrieval"""
        response = client.get("/api/ingest/stats")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["collection"] == "zantara_books"
        assert result["total_documents"] == 1000
        assert "tiers_distribution" in result
        assert result["tiers_distribution"]["S"] == 50
        assert result["tiers_distribution"]["A"] == 200
        assert result["persist_directory"] == "/data/qdrant"

        # Verify client was called
        mock_qdrant_client.get_collection_stats.assert_called_once()

    def test_get_stats_no_tier_distribution(self, client, mock_qdrant_client):
        """Test stats when tier distribution is not available"""
        mock_qdrant_client.get_collection_stats.return_value = {
            "collection_name": "test_collection",
            "total_documents": 500,
            "persist_directory": "/data",
        }

        response = client.get("/api/ingest/stats")

        assert response.status_code == 200
        result = response.json()
        assert result["tiers_distribution"] == {}

    def test_get_stats_client_error(self, client, mock_qdrant_client):
        """Test stats when Qdrant client fails"""
        mock_qdrant_client.get_collection_stats.side_effect = Exception("Connection failed")

        response = client.get("/api/ingest/stats")

        assert response.status_code == 500
        assert "Failed to get stats" in response.json()["detail"]
        assert "Connection failed" in response.json()["detail"]

    def test_get_stats_empty_collection(self, client, mock_qdrant_client):
        """Test stats with empty collection"""
        mock_qdrant_client.get_collection_stats.return_value = {
            "collection_name": "empty_collection",
            "total_documents": 0,
            "tiers_distribution": {},
            "persist_directory": "/data/qdrant",
        }

        response = client.get("/api/ingest/stats")

        assert response.status_code == 200
        result = response.json()
        assert result["total_documents"] == 0
        assert result["tiers_distribution"] == {}


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIngestRouterIntegration:
    """Integration tests for the complete ingest router"""

    def test_upload_then_check_stats(
        self, client, mock_ingestion_service, mock_qdrant_client, sample_pdf_content
    ):
        """Test uploading a book and then checking stats"""
        # First upload a book
        with (
            patch("backend.app.routers.ingest.open", mock_open()),
            patch("backend.app.routers.ingest.os.remove"),
            patch("backend.app.routers.ingest.Path") as mock_path,
        ):
            mock_temp_dir = MagicMock()
            mock_temp_path = MagicMock()
            mock_temp_path.exists.return_value = True
            mock_path.return_value = mock_temp_dir
            mock_temp_dir.__truediv__ = MagicMock(return_value=mock_temp_path)

            files = {"file": ("test.pdf", BytesIO(sample_pdf_content), "application/pdf")}
            upload_response = client.post("/api/ingest/upload", files=files)
            assert upload_response.status_code == 200

        # Then check stats
        stats_response = client.get("/api/ingest/stats")
        assert stats_response.status_code == 200
        assert stats_response.json()["total_documents"] >= 0

    def test_multiple_endpoints_share_service(self, client, mock_ingestion_service):
        """Test that multiple endpoints can use the service"""
        with patch("backend.app.routers.ingest.os.path.exists", return_value=True):
            # Call file endpoint
            response1 = client.post("/api/ingest/file", json={"file_path": "/data/book1.pdf"})
            assert response1.status_code == 200

            # Call again
            response2 = client.post("/api/ingest/file", json={"file_path": "/data/book2.pdf"})
            assert response2.status_code == 200

            # Service should be called twice
            assert mock_ingestion_service.ingest_book.call_count == 2


# ============================================================================
# EDGE CASES AND ERROR SCENARIOS
# ============================================================================


class TestEdgeCases:
    """Test edge cases and unusual scenarios"""

    def test_upload_very_large_filename(self, client, mock_ingestion_service, sample_pdf_content):
        """Test upload with very long filename"""
        with (
            patch("backend.app.routers.ingest.open", mock_open()),
            patch("backend.app.routers.ingest.os.remove"),
            patch("backend.app.routers.ingest.Path") as mock_path,
        ):
            mock_temp_dir = MagicMock()
            mock_temp_path = MagicMock()
            mock_temp_path.exists.return_value = True
            mock_path.return_value = mock_temp_dir
            mock_temp_dir.__truediv__ = MagicMock(return_value=mock_temp_path)

            long_name = "a" * 200 + ".pdf"
            files = {"file": (long_name, BytesIO(sample_pdf_content), "application/pdf")}

            response = client.post("/api/ingest/upload", files=files)

            # Should still work
            assert response.status_code == 200

    def test_upload_special_characters_in_filename(
        self, client, mock_ingestion_service, sample_pdf_content
    ):
        """Test upload with special characters in filename"""
        with (
            patch("backend.app.routers.ingest.open", mock_open()),
            patch("backend.app.routers.ingest.os.remove"),
            patch("backend.app.routers.ingest.Path") as mock_path,
        ):
            mock_temp_dir = MagicMock()
            mock_temp_path = MagicMock()
            mock_temp_path.exists.return_value = True
            mock_path.return_value = mock_temp_dir
            mock_temp_dir.__truediv__ = MagicMock(return_value=mock_temp_path)

            files = {
                "file": ("book_with_émojis_😀.pdf", BytesIO(sample_pdf_content), "application/pdf")
            }

            response = client.post("/api/ingest/upload", files=files)

            assert response.status_code == 200

    def test_file_ingest_empty_path(self, client):
        """Test file ingestion with empty file path"""
        response = client.post("/api/ingest/file", json={"file_path": ""})

        # Should fail validation or file not found
        assert response.status_code in [404, 422]

    def test_batch_ingest_empty_patterns_list(self, client, mock_ingestion_service):
        """Test batch ingestion with empty patterns list"""
        with patch("backend.app.routers.ingest.Path") as mock_path_class:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_path_class.return_value = mock_dir
            mock_dir.glob.return_value = []

            request_data = {
                "directory_path": "/data/books",
                "file_patterns": [],
            }

            response = client.post("/api/ingest/batch", json=request_data)

            # Should find no books
            assert response.status_code == 400
            assert "No books found" in response.json()["detail"]

    def test_upload_case_insensitive_extension(
        self, client, mock_ingestion_service, sample_pdf_content
    ):
        """Test upload with uppercase extension"""
        with (
            patch("backend.app.routers.ingest.open", mock_open()),
            patch("backend.app.routers.ingest.os.remove"),
            patch("backend.app.routers.ingest.Path") as mock_path,
        ):
            mock_temp_dir = MagicMock()
            mock_temp_path = MagicMock()
            mock_temp_path.exists.return_value = True
            mock_path.return_value = mock_temp_dir
            mock_temp_dir.__truediv__ = MagicMock(return_value=mock_temp_path)

            # Note: Current implementation is case-sensitive
            # This test documents the current behavior
            files = {"file": ("test.PDF", BytesIO(sample_pdf_content), "application/pdf")}

            response = client.post("/api/ingest/upload", files=files)

            # Will fail with current implementation (case-sensitive)
            assert response.status_code == 400

    def test_stats_with_malformed_response(self, client, mock_qdrant_client):
        """Test stats when Qdrant returns unexpected format"""
        mock_qdrant_client.get_collection_stats.return_value = {"unexpected_field": "value"}

        response = client.get("/api/ingest/stats")

        # Should handle KeyError gracefully
        # This might raise 500 or return partial data depending on implementation
        # The test documents current behavior
        assert response.status_code in [200, 500]
```

---


---

## 📝 P2 - Medium Priority

✅ No medium priority issues!

---

## 📋 P3 - Low Priority (Sample)

### TODO - P3

**File:** `apps/backend-rag/apps/mouth/src/app/(workspace)/intelligence/system-pulse/page.tsx:39`

**Component:** backend

**Content:**
```
// TODO: Replace with real API call when backend endpoint is ready
    setTimeout(() => {
      setMetrics({
        agent_status: "active",
        last_run: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
        items_processed_today: 29,
        avg_response_time_ms: 1250,
        qdrant_health: "healthy",
        next_scheduled_run: new Date(Date.now() + 1000 * 60 * 45).toISOString(), // 45 min from now
        uptime_percentage: 99.8,
      });
      setLoading(false);
    }, 800);
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Loading System Metrics...
        </p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <AlertCircle className="h-16 w-16 text-red-500 mb-4" />
        <h3 className="text-xl font-semibold text-[var(--foreground)] mb-2">
          Metrics Unavailable
        </h3>
        <p className="text-[var(--foreground-muted)] mb-6">
          Unable to load system health metrics
        </p>
        <Button onClick={loadMetrics} variant="outline" className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
      </div>
    );
  }

  const statusColor = {
    active: "text-green-600",
    idle: "text-amber-600",
    error: "text-red-600",
  }[metrics.agent_status];

  const statusBgColor = {
    active: "bg-green-100 border-green-200",
    idle: "bg-amber-100 border-amber-200",
    error: "bg-red-100 border-red-200",
  }[metrics.agent_status];

  const qdrantColor = {
    healthy: "text-green-600",
    degraded: "text-amber-600",
    down: "text-red-600",
  }[metrics.qdrant_health];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-center pb-4 border-b border-[var(--border)]">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            System Pulse
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Real-time health monitoring for IntelligentVisaAgent
          </p>
        </div>
        <Button onClick={loadMetrics} variant="secondary" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Agent Status */}
        <Card className="border-t-4 border-t-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Agent Status
            </CardTitle>
            <Activity className={cn("h-5 w-5", statusColor)} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-bold border shadow-sm",
                  statusBgColor,
                  statusColor
                )}
              >
                <div className="w-2 h-2 rounded-full bg-current animate-pulse" />
                {metrics.agent_status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-3">
              Uptime: {metrics.uptime_percentage}%
            </p>
          </CardContent>
        </Card>

        {/* Last Run */}
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Last Scan
            </CardTitle>
            <Clock className="h-5 w-5 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {new Date(metrics.last_run).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              {new Date(metrics.last_run).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </p>
          </CardContent>
        </Card>

        {/* Items Processed */}
        <Card className="border-t-4 border-t-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Items Processed Today
            </CardTitle>
            <TrendingUp className="h-5 w-5 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {metrics.items_processed_today}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Visa pages analyzed
            </p>
          </CardContent>
        </Card>

        {/* Avg Response Time */}
        <Card className="border-t-4 border-t-amber-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Avg Response Time
            </CardTitle>
            <Zap className="h-5 w-5 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {(metrics.avg_response_time_ms / 1000).toFixed(2)}s
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Per page analysis
            </p>
          </CardContent>
        </Card>

        {/* Qdrant Health */}
        <Card className="border-t-4 border-t-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Qdrant Health
            </CardTitle>
            <Database className={cn("h-5 w-5", qdrantColor)} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {metrics.qdrant_health === "healthy" && (
                <CheckCircle className="h-5 w-5 text-green-600" />
              )}
              {metrics.qdrant_health === "degraded" && (
                <AlertCircle className="h-5 w-5 text-amber-600" />
              )}
              {metrics.qdrant_health === "down" && (
                <AlertCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={cn("text-lg font-bold", qdrantColor)}>
                {metrics.qdrant_health.charAt(0).toUpperCase() +
                  metrics.qdrant_health.slice(1)}
              </span>
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Vector database status
            </p>
          </CardContent>
        </Card>

        {/* Next Scheduled Run */}
        <Card className="border-t-4 border-t-slate-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Next Scheduled Run
            </CardTitle>
            <Clock className="h-5 w-5 text-slate-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {new Date(metrics.next_scheduled_run).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Every 2 hours
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Agent Configuration Info */}
      <Card className="bg-[var(--background-secondary)] border-[var(--border)]">
        <CardHeader>
          <CardTitle className="text-lg text-[var(--foreground)]">
            Agent Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Model</p>
              <p className="text-[var(--foreground)]">Gemini 2.0 Flash (Vision)</p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Browser</p>
              <p className="text-[var(--foreground)]">Playwright Webkit</p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Target URL</p>
              <p className="text-[var(--foreground)] text-xs font-mono">
                imigrasi.go.id/wna/permohonan-visa
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Detection Mode</p>
              <p className="text-[var(--foreground)]">MD5 Hash + Vision Analysis</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/autonomous_agents.py:617`

**Component:** backend

**Assignee:** @router

**Content:**
```
# TODO: Get from scheduler if available
            "success_rate": round(success_rate, 1) if success_rate is not None else None,
            "total_runs": total_runs,
            "latest_result": latest_result,
        }

    # Agent definitions with stats
    agents_data = [
        {
            "name": "Conversation Quality Trainer",
            "description": "Learns from successful conversations and improves prompts",
            **get_agent_stats("conversation_trainer"),
        },
        {
            "name": "Client LTV Predictor & Nurturer",
            "description": "Predicts client value and sends personalized nurturing messages",
            **get_agent_stats("client_value_predictor"),
        },
        {
            "name": "Knowledge Graph Builder",
            "description": "Extracts entities and relationships from all data sources",
            **get_agent_stats("knowledge_graph_builder"),
        },
    ]

    return {
        "success": True,
        "tier": 1,
        "total_agents": 3,
        "agents": agents_data,
        "recent_executions": len(agent_executions),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/executions/{execution_id}", response_model=AgentExecutionResponse)
async def get_execution_status(execution_id: str):
    """
    Get status of a specific agent execution

    Args:
        execution_id: Execution ID returned by agent run endpoint

    Returns:
        Execution details and result
    """
    if execution_id not in agent_executions:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution_data = agent_executions[execution_id].copy()
    execution_data["execution_id"] = execution_id
    return AgentExecutionResponse(**execution_data)


@router.get("/executions")
async def list_executions(limit: int = 20):
    """
    List recent agent executions

    Args:
        limit: Maximum number of executions to return (default: 20)

    Returns:
        List of recent executions
    """
    executions = sorted(
        agent_executions.items(), key=lambda x: x[1].get("started_at", ""), reverse=True
    )[:limit]

    return {
        "success": True,
        "executions": [{**data, "execution_id": exec_id} for exec_id, data in executions],
        "total": len(agent_executions),
    }


# ============================================================================
# AUTONOMOUS SCHEDULER STATUS & CONTROL
# ============================================================================


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    🤖 Get status of the Autonomous Scheduler and all registered tasks

    Returns:
        Scheduler status with task details:
        - running: Whether scheduler is active
        - task_count: Number of registered tasks
        - tasks: Details of each task (intervals, run counts, errors)
    """
    try:
        from backend.services.misc.autonomous_scheduler import get_autonomous_scheduler

        scheduler = get_autonomous_scheduler()
        status = scheduler.get_status()

        return {
            "success": True,
            "scheduler": status,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/scheduler/task/{task_name}/enable")
async def enable_scheduler_task(task_name: str):
    """
    ✅ Enable a scheduled task

    Args:
        task_name: Name of the task to enable
    """
    try:
        from backend.services.misc.autonomous_scheduler import get_autonomous_scheduler

        scheduler = get_autonomous_scheduler()
        success = scheduler.enable_task(task_name)

        if success:
            return {
                "success": True,
                "message": f"Task '{task_name}' enabled",
                "task_name": task_name,
            }
        else:
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/task/{task_name}/disable")
async def disable_scheduler_task(task_name: str):
    """
    ⏸️ Disable a scheduled task

    Args:
        task_name: Name of the task to disable
    """
    try:
        from backend.services.misc.autonomous_scheduler import get_autonomous_scheduler

        scheduler = get_autonomous_scheduler()
        success = scheduler.disable_task(task_name)

        if success:
            return {
                "success": True,
                "message": f"Task '{task_name}' disabled",
                "task_name": task_name,
            }
        else:
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/dashboard_summary.py:116`

**Component:** backend

**Assignee:** @router

**Content:**
```
# TODO: Add revenue growth when implemented
                    asyncio.sleep(0),  # Placeholder for revenue growth
                ]
            )

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results with fallbacks
        practice_stats = (
            results[0] if not isinstance(results[0], Exception) else DEFAULT_PRACTICE_STATS
        )
        interaction_stats = (
            results[1] if not isinstance(results[1], Exception) else DEFAULT_INTERACTION_STATS
        )
        practices = results[2] if not isinstance(results[2], Exception) else []
        interactions = results[3] if not isinstance(results[3], Exception) else []
        email_stats = (
            results[4]
            if not isinstance(results[4], Exception)
            else {"connected": False, "unread_count": 0}
        )

        # Check system health
        has_failures = any(isinstance(result, Exception) for result in results[:5])
        system_status = "healthy" if not has_failures else "degraded"

        # Map practices to preview format
        mapped_practices = []
        for practice in practices[:5]:
            # Map backend status to frontend valid status
            backend_status = practice.get("status", "inquiry").lower()
            status_map = {
                "in_progress": "in_progress",
                "completed": "completed",
                "inquiry": "inquiry",
                "quotation": "quotation",
                "documents": "documents",
                "unknown": "inquiry",
                "new": "inquiry",
                "pending": "inquiry",
            }
            frontend_status = status_map.get(backend_status, "inquiry")

            mapped_practices.append(
                {
                    "id": practice.get("id"),
                    "title": practice.get("practice_type_code", "").upper().replace("_", " ")
                    or "Case",
                    "client": practice.get("client_name", "Unknown Client"),
                    "status": frontend_status,
                    "daysRemaining": (
                        (practice["expiry_date"] - datetime.now().date()).days
                        if practice.get("expiry_date")
                        else None
                    ),
                }
            )

        # Map interactions to WhatsApp format
        mapped_interactions = []
        for interaction in interactions[:5]:
            mapped_interactions.append(
                {
                    "id": str(interaction.get("id")),
                    "contactName": interaction.get("client_name", "Anonymous"),
                    "message": interaction.get("summary")
                    or interaction.get("full_content", "No content"),
                    "timestamp": interaction.get("created_at", "")[:8]
                    if interaction.get("created_at")
                    else "",
                    "isRead": interaction.get("read_receipt") is True,
                    "hasAiSuggestion": bool(interaction.get("conversation_id")),
                    "practiceId": interaction.get("practice_id"),
                }
            )

        # Calculate stats
        hours_worked = float(interaction_stats.get("total_interactions", 0) * 0.25)  # Estimate

        return {
            "user": {
                "email": current_user.get("email", ""),
                "role": current_user.get("role", ""),
                "is_admin": is_admin,
            },
            "stats": {
                "activeCases": practice_stats.get("active_practices", 0),
                "criticalDeadlines": 0,  # TODO: Implement renewals
                "whatsappUnread": interaction_stats.get("by_type", {}).get("whatsapp", 0),
                "emailUnread": email_stats.get("unread_count", 0),
                "hoursWorked": f"{int(hours_worked)}h {int((hours_worked % 1) * 60)}m",
            },
            "data": {
                "practices": mapped_practices,
                "interactions": mapped_interactions,
                "email": email_stats,
            },
            "system_status": system_status,
            "last_updated": asyncio.get_event_loop().time(),
        }

    except Exception as e:
        logger.error(f"Failed to get dashboard summary for user {user_id}: {e}")
        # Return degraded response
        return {
            "user": {
                "email": current_user.get("email", ""),
                "role": current_user.get("role", ""),
                "is_admin": is_admin,
            },
            "stats": {
                "activeCases": 0,
                "criticalDeadlines": 0,
                "whatsappUnread": 0,
                "emailUnread": 0,
                "hoursWorked": "0h 0m",
            },
            "data": {
                "practices": [],
                "interactions": [],
                "email": {"connected": False, "unread_count": 0},
            },
            "system_status": "degraded",
            "last_updated": asyncio.get_event_loop().time(),
        }


@router.get("/neural-pulse")
async def get_neural_pulse(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get real-time AI status metrics (Neural Pulse).
    """
    start_time = time.time()
    try:
        # 1. Get memory facts count
        memory_service = CollectiveMemoryService(pool=db_pool)
        memory_stats = await memory_service.get_stats()
        memory_facts = memory_stats.get("total_facts", 0)

        # 2. Get knowledge docs count (from Qdrant)
        knowledge_docs = 0
        try:
            qdrant = QdrantClient(qdrant_url=settings.qdrant_url, collection_name="knowledge_base")
            qdrant_stats = await qdrant.get_stats()
            knowledge_docs = qdrant_stats.get("total_documents", 0)
            await qdrant.close()
        except Exception as e:
            logger.warning(f"Failed to get Qdrant stats for pulse: {e}")

        # 3. Get last activity
        last_activity = "Initializing neural link..."
        try:
            async with db_pool.acquire() as conn:
                # Check last conversation or interaction
                # We check multiple tables to find the most recent activity
                last_conv = await conn.fetchval(
                    "SELECT content FROM conversation_messages ORDER BY created_at DESC LIMIT 1"
                )
                if last_conv:
                    last_activity = f"Last chat: {last_conv[:30]}..."
                else:
                    last_int = await conn.fetchval(
                        "SELECT summary FROM crm_interactions ORDER BY created_at DESC LIMIT 1"
                    )
                    if last_int:
                        last_activity = f"Last CRM: {last_int[:30]}..."

        except Exception as e:
            logger.warning(f"Failed to get last activity for pulse: {e}")

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "status": "healthy",
            "memory_facts": memory_facts or 42,  # Fallback to 42 if 0 for visual pulse
            "knowledge_docs": knowledge_docs or 53757,  # Legacy fallback
            "latency_ms": latency_ms,
            "model_version": "Gemini 1.5 Pro",
            "last_activity": last_activity,
        }
    except Exception as e:
        logger.error(f"Failed to generate neural pulse: {e}")
        return {
            "status": "degraded",
            "memory_facts": 0,
            "knowledge_docs": 0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "model_version": "Gemini 1.5 Pro",
            "last_activity": "System heartbeat failing",
        }
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/debug.py:132`

**Component:** backend

**Assignee:** @router

**Content:**
```
# TODO: Integrate with actual logging service
    return {
        "success": True,
        "message": "Log retrieval not yet implemented. Integrate with logging service.",
        "filters": {
            "module": module,
            "level": level,
            "limit": limit,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/state")
async def get_app_state(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get internal application state.

    Args:
        request: FastAPI request

    Returns:
        Application state information
    """
    app_state = request.app.state

    state_info: dict[str, Any] = {
        "services": {},
        "initialized": getattr(app_state, "services_initialized", False),
        "correlation_id": get_correlation_id(request),
    }

    # Check key services
    service_checks = [
        "search_service",
        "ai_client",
        "db_pool",
        "memory_service",
        "intelligent_router",
        "tool_executor",
    ]

    for service_name in service_checks:
        service = getattr(app_state, service_name, None)
        state_info["services"][service_name] = {
            "present": service is not None,
            "type": type(service).__name__ if service else None,
        }

    return {
        "success": True,
        "state": state_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/services")
async def get_services_status(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get status of all services.

    Args:
        request: FastAPI request

    Returns:
        Services status
    """
    from backend.app.core.service_health import service_registry

    services_status: dict[str, Any] = {}

    # Get service registry status if available
    try:
        registry_status = service_registry.get_status()
        services_status["registry"] = registry_status
    except Exception as e:
        logger.warning(f"Failed to get service registry status: {e}")
        services_status["registry"] = {"error": str(e)}

    # Check individual services
    app_state = request.app.state
    service_checks = [
        "search_service",
        "ai_client",
        "db_pool",
        "memory_service",
        "intelligent_router",
        "health_monitor",
    ]

    for service_name in service_checks:
        service = getattr(app_state, service_name, None)
        if service:
            try:
                # Try to get health status if available
                if hasattr(service, "health_check"):
                    health = await service.health_check()
                    services_status[service_name] = health
                else:
                    services_status[service_name] = {
                        "status": "available",
                        "type": type(service).__name__,
                    }
            except Exception as e:
                services_status[service_name] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            services_status[service_name] = {"status": "unavailable"}

    return {
        "success": True,
        "services": services_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/traces/recent")
async def get_recent_traces_endpoint(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of traces"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get recent request traces.

    Args:
        limit: Maximum number of traces to return

    Returns:
        Recent traces
    """
    traces = RequestTracingMiddleware.get_recent_traces(limit=limit)

    return {
        "success": True,
        "traces": traces,
        "count": len(traces),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/traces")
async def clear_traces(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Clear all stored traces.

    Returns:
        Confirmation message
    """
    from middleware.request_tracing import RequestTracingMiddleware

    count = RequestTracingMiddleware.clear_traces()

    return {
        "success": True,
        "message": f"Cleared {count} traces",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/rag/pipeline/{correlation_id}")
async def get_rag_pipeline_trace(
    correlation_id: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get RAG pipeline trace for a correlation ID.

    Note: This requires RAG pipeline to use RAGPipelineDebugger.

    Args:
        correlation_id: Correlation ID

    Returns:
        RAG pipeline trace
    """
    # TODO: Implement RAG pipeline trace storage
    return {
        "success": False,
        "message": "RAG pipeline tracing not yet implemented. Use RAGPipelineDebugger in pipeline.",
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/slow")
async def get_slow_queries(
    limit: int = Query(50, ge=1, le=500),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get slow database queries.

    Args:
        limit: Maximum number of queries to return

    Returns:
        Slow queries list
    """
    from backend.app.utils.db_debugger import DatabaseQueryDebugger

    slow_queries = DatabaseQueryDebugger.get_slow_queries(limit=limit)

    return {
        "success": True,
        "queries": slow_queries,
        "count": len(slow_queries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/recent")
async def get_recent_queries(
    limit: int = Query(100, ge=1, le=1000),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get recent database queries.

    Args:
        limit: Maximum number of queries to return

    Returns:
        Recent queries list
    """
    from backend.app.utils.db_debugger import DatabaseQueryDebugger

    recent_queries = DatabaseQueryDebugger.get_recent_queries(limit=limit)

    return {
        "success": True,
        "queries": recent_queries,
        "count": len(recent_queries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/analyze")
async def analyze_query_patterns(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Analyze database query patterns.

    Returns:
        Query pattern analysis
    """
    from backend.app.utils.db_debugger import DatabaseQueryDebugger

    analysis = DatabaseQueryDebugger.analyze_query_patterns()

    return {
        "success": True,
        "analysis": analysis,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/qdrant/collections/health")
async def get_qdrant_collections_health(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get health status of all Qdrant collections.

    Returns:
        Collections health status
    """
    from backend.app.utils.qdrant_debugger import QdrantDebugger

    debugger = QdrantDebugger()
    health_statuses = await debugger.get_all_collections_health()

    return {
        "success": True,
        "collections": [
            {
                "name": h.name,
                "points_count": h.points_count,
                "vectors_count": h.vectors_count,
                "indexed": h.indexed,
                "status": h.status,
                "error": h.error,
            }
            for h in health_statuses
        ],
        "count": len(health_statuses),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/qdrant/collection/{collection_name}/stats")
async def get_collection_stats(
    collection_name: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get detailed statistics for a Qdrant collection.

    Args:
        collection_name: Collection name

    Returns:
        Collection statistics
    """
    from backend.app.utils.qdrant_debugger import QdrantDebugger

    debugger = QdrantDebugger()
    stats = await debugger.get_collection_stats(collection_name)

    return {
        "success": True,
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/parent-documents-public/{document_id}")
async def get_parent_documents_public(
    document_id: str,
) -> dict[str, Any]:
    """
    Get parent documents (BAB) from PostgreSQL for a legal document.
    PUBLIC endpoint for testing - NO AUTH REQUIRED.

    Args:
        document_id: Document ID (e.g. "PP_31_2013")

    Returns:
        List of BAB (chapters) with metadata
    """
    import asyncpg

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        # Query parent_documents table
        rows = await conn.fetch(
            """
            SELECT id, document_id, type, title,
                   char_count, pasal_count,
                   created_at
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
            """,
            document_id,
        )

        await conn.close()

        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "type": row["type"],
                    "title": row["title"],
                    "char_count": row["char_count"],
                    "pasal_count": row["pasal_count"],
                    "created_at": str(row["created_at"]),
                }
            )

        return {
            "success": True,
            "document_id": document_id,
            "total_bab": len(results),
            "bab_list": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to query parent_documents: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/parent-documents/{document_id}/{bab_id}/text")
async def get_bab_full_text(
    document_id: str,
    bab_id: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get full text of a specific BAB from PostgreSQL.

    Args:
        document_id: Document ID
        bab_id: BAB ID (e.g. "PP_31_2013_BAB_III")

    Returns:
        Full text of the BAB
    """
    import asyncpg

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        row = await conn.fetchrow(
            """
            SELECT id, title, full_text,
                   char_count, pasal_count
            FROM parent_documents
            WHERE document_id = $1 AND id = $2
            """,
            document_id,
            bab_id,
        )

        await conn.close()

        if not row:
            return {
                "success": False,
                "error": "BAB not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "success": True,
            "id": row["id"],
            "title": row["title"],
            "char_count": row["char_count"],
            "pasal_count": row["pasal_count"],
            "full_text": row["full_text"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to query BAB text: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/profile")
async def run_performance_profiling(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Run performance profiling analysis.

    Note: This integrates with the existing performance_profiler.py script.
    For full analysis, use the script directly: python scripts/performance_profiler.py

    Returns:
        Profiling results summary
    """
    import sys
    from pathlib import Path

    # Import the profiler class
    profiler_script_path = (
        Path(__file__).parent.parent.parent.parent.parent / "scripts" / "performance_profiler.py"
    )

    if not profiler_script_path.exists():
        return {
            "success": False,
            "message": "Performance profiler script not found",
            "path": str(profiler_script_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    try:
        # Import profiler class
        sys.path.insert(0, str(profiler_script_path.parent))
        from performance_profiler import PerformanceProfiler

        # Run profiling - use hostname from request or settings
        # PRODUCTION: Use actual hostname instead of hardcoded localhost
        hostname = getattr(request.app.state, "hostname", None) or settings.hostname or "localhost"
        base_url = (
            f"http://{hostname}:{settings.port}"
            if hostname != "localhost"
            else f"http://localhost:{settings.port}"
        )
        profiler = PerformanceProfiler(base_url=base_url)
        results = await profiler.run_profiling()

        return {
            "success": True,
            "results": {
                "priority_areas": results.get("priorities", {}),
                "database_analysis": results.get("database", {}),
                "code_patterns": results.get("code_patterns", {}),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Performance profiling failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Performance profiling failed. Use script directly: python scripts/performance_profiler.py",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ========================================
# PostgreSQL Debug Endpoints
# ========================================


class QueryRequest(BaseModel):
    """Request model for custom query execution"""

    query: str
    limit: int = 100


@router.get("/postgres/connection")
async def get_postgres_connection(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Test PostgreSQL connection and get connection info.

    Args:
        request: FastAPI request (to access app.state for pool)

    Returns:
        Connection information and status
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    # Try to get pool from backend.app.state if available
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        # Try memory_service pool
        memory_service = getattr(request.app.state, "memory_service", None)
        if memory_service and hasattr(memory_service, "pool"):
            pool = memory_service.pool

    try:
        conn_info = await debugger.test_connection(pool=pool)
        return {
            "success": True,
            "connection": {
                "connected": conn_info.connected,
                "version": conn_info.version,
                "database": conn_info.database,
                "user": conn_info.user,
                "pool_size": conn_info.pool_size,
                "pool_idle": conn_info.pool_idle,
                "pool_active": conn_info.pool_active,
            },
            "error": conn_info.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/postgres/schema/tables")
async def get_postgres_tables(
    schema: str = Query("public", description="Schema name"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get list of all tables in a schema.

    Args:
        schema: Schema name (default: public)

    Returns:
        List of tables
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        tables = await debugger.get_tables(schema=schema)
        return {
            "success": True,
            "schema": schema,
            "tables": tables,
            "count": len(tables),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/schema/table/{table_name}")
async def get_postgres_table_details(
    table_name: str,
    schema: str = Query("public", description="Schema name"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get detailed information about a table.

    Args:
        table_name: Table name
        schema: Schema name (default: public)

    Returns:
        Table details including columns, indexes, foreign keys, constraints
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        table_info = await debugger.get_table_details(table_name=table_name, schema=schema)
        return {
            "success": True,
            "table": {
                "schema": table_info.schema,
                "name": table_info.name,
                "columns": table_info.columns,
                "indexes": table_info.indexes,
                "foreign_keys": table_info.foreign_keys,
                "constraints": table_info.constraints,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get table details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/schema/indexes")
async def get_postgres_indexes(
    table_name: str | None = Query(None, description="Optional table name filter"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get list of all indexes.

    Args:
        table_name: Optional table name to filter indexes

    Returns:
        List of indexes
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        indexes = await debugger.get_indexes(table_name=table_name)
        return {
            "success": True,
            "indexes": indexes,
            "count": len(indexes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get indexes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/stats/tables")
async def get_postgres_table_stats(
    table_name: str | None = Query(None, description="Optional table name filter"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get statistics for tables (row counts, sizes, indexes).

    Args:
        table_name: Optional table name to filter stats

    Returns:
        Table statistics
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_table_stats(table_name=table_name)
        return {
            "success": True,
            "stats": stats,
            "count": len(stats),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get table stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/stats/database")
async def get_postgres_database_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get global database statistics.

    Returns:
        Database statistics
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_database_stats()
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/postgres/query")
async def execute_postgres_query(
    query_request: QueryRequest = Body(...),
    request: Request = None,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Execute a read-only query safely.

    Args:
        query_request: Query request with SQL and limit
        request: FastAPI request (to access app.state for pool)

    Returns:
        Query results
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    # Try to get pool from backend.app.state if available
    pool = None
    if request:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            memory_service = getattr(request.app.state, "memory_service", None)
            if memory_service and hasattr(memory_service, "pool"):
                pool = memory_service.pool

    try:
        results = await debugger.execute_query(
            query=query_request.query, limit=query_request.limit, pool=pool
        )
        return {
            "success": True,
            **results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        # Query validation failed
        logger.warning(f"Query validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/slow-queries")
async def get_postgres_slow_queries(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of queries"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get slow queries from pg_stat_statements (if available).

    Args:
        limit: Maximum number of queries to return

    Returns:
        Slow queries list
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        queries = await debugger.get_slow_queries(limit=limit)
        return {
            "success": True,
            "queries": queries,
            "count": len(queries),
            "extension_available": len(queries) > 0
            or True,  # Will be empty if extension not available
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get slow queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/locks")
async def get_postgres_locks(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get active locks in the database.

    Returns:
        Active locks list
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        locks = await debugger.get_active_locks()
        return {
            "success": True,
            "locks": locks,
            "count": len(locks),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get locks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/connections")
async def get_postgres_connection_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get connection statistics.

    Returns:
        Connection statistics
    """
    from backend.app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_connection_stats()
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Sentry Test Endpoint (v1 compatibility) ---
@v1_router.get("/sentry-test")
async def sentry_test_error(
    _current_user: dict = Depends(get_current_user),
):
    """
    Trigger a test error for Sentry monitoring verification.
    This endpoint intentionally raises an exception to test Sentry integration.

    SECURITY: Requires authentication to prevent abuse.
    """
    logger.warning("🧪 Sentry test endpoint triggered - about to raise exception")
    # This will be caught by Sentry
    raise ValueError(
        "🧪 TEST ERROR: This is a controlled test error for Sentry verification. If you see this in Sentry, the integration is working correctly!"
    )
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/feedback.py:219`

**Component:** backend

**Content:**
```
# TODO: Add admin authentication check
        # For now, this is a mock endpoint

        async with db_pool.acquire() as conn:
            # Get review queue stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as total_pending,
                    COUNT(*) FILTER (WHERE status = 'resolved') as total_resolved,
                    COUNT(*) FILTER (WHERE status = 'ignored') as total_ignored,
                    COUNT(*) as total_reviews
                FROM review_queue
                """
            )

            # Get low ratings count (ratings <= 2)
            low_ratings = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM conversation_ratings
                WHERE rating <= 2
                """
            )

            # Get corrections count (feedbacks with correction_text)
            # Note: We don't have correction_text column in conversation_ratings yet
            # This is a placeholder for future implementation
            corrections_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM review_queue rq
                JOIN conversation_ratings cr ON rq.source_feedback_id = cr.id
                WHERE cr.feedback_text IS NOT NULL AND cr.feedback_text != ''
                """
            )

            return ReviewQueueStatsResponse(
                total_pending=stats["total_pending"] or 0,
                total_resolved=stats["total_resolved"] or 0,
                total_ignored=stats["total_ignored"] or 0,
                total_reviews=stats["total_reviews"] or 0,
                low_ratings_count=low_ratings or 0,
                corrections_count=corrections_count or 0,
            )

    except Exception as e:
        logger.error(f"Error retrieving feedback stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/newsletter.py:204`

**Component:** backend

**Assignee:** @router

**Content:**
```
# TODO: Send confirmation email via Zoho
        # await send_confirmation_email(request.email, subscriber_id, confirmation_token)

        return SubscribeResponse(
            success=True,
            message="Please check your email to confirm your subscription.",
            subscriberId=subscriber_id,
        )


@router.post("/confirm")
async def confirm_subscription(request: ConfirmRequest, pool=Depends(get_database_pool)):
    """
    Confirm a newsletter subscription using the token from email.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, confirmed FROM newsletter_subscribers
            WHERE id = $1 AND confirmation_token = $2
            """,
            request.subscriberId,
            request.token,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Invalid confirmation link")

        if row["confirmed"]:
            return {"success": True, "message": "Subscription already confirmed"}

        await conn.execute(
            """
            UPDATE newsletter_subscribers
            SET confirmed = TRUE,
                confirmed_at = NOW(),
                confirmation_token = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            request.subscriberId,
        )

        logger.info(f"Confirmed subscription: {row['email']}")
        return {"success": True, "message": "Subscription confirmed successfully"}


@router.post("/unsubscribe")
async def unsubscribe(request: UnsubscribeRequest, pool=Depends(get_database_pool)):
    """
    Unsubscribe from the newsletter.
    """
    async with pool.acquire() as conn:
        # Find subscriber by ID, email, or token
        if request.subscriberId:
            row = await conn.fetchrow(
                "SELECT id, email FROM newsletter_subscribers WHERE id = $1", request.subscriberId
            )
        elif request.email:
            row = await conn.fetchrow(
                "SELECT id, email FROM newsletter_subscribers WHERE email = $1", request.email
            )
        else:
            raise HTTPException(status_code=400, detail="Email or subscriberId required")

        if not row:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        await conn.execute(
            """
            UPDATE newsletter_subscribers
            SET unsubscribed_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
        )

        logger.info(f"Unsubscribed: {row['email']}")
        return {"success": True, "message": "Successfully unsubscribed"}


@router.patch("/preferences")
async def update_preferences(request: PreferencesRequest, pool=Depends(get_database_pool)):
    """
    Update newsletter preferences.
    """
    async with pool.acquire() as conn:
        # Find subscriber
        if request.subscriberId:
            row = await conn.fetchrow(
                "SELECT id FROM newsletter_subscribers WHERE id = $1", request.subscriberId
            )
        elif request.email:
            row = await conn.fetchrow(
                "SELECT id FROM newsletter_subscribers WHERE email = $1", request.email
            )
        else:
            raise HTTPException(status_code=400, detail="Email or subscriberId required")

        if not row:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        # Build dynamic update
        updates = []
        params = [row["id"]]
        param_idx = 2

        if request.categories is not None:
            updates.append(f"categories = ${param_idx}")
            params.append(request.categories)
            param_idx += 1

        if request.frequency is not None:
            updates.append(f"frequency = ${param_idx}")
            params.append(request.frequency)
            param_idx += 1

        if request.language is not None:
            updates.append(f"language = ${param_idx}")
            params.append(request.language)
            param_idx += 1

        if not updates:
            return {"success": True, "message": "No changes"}

        updates.append("updated_at = NOW()")
        query = f"UPDATE newsletter_subscribers SET {', '.join(updates)} WHERE id = $1"
        await conn.execute(query, *params)

        logger.info(f"Updated preferences for subscriber: {row['id']}")
        return {"success": True, "message": "Preferences updated"}


@router.get("/subscribers")
async def list_subscribers(
    category: str | None = Query(None),
    frequency: str | None = Query(None),
    confirmed: bool | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    pool=Depends(get_database_pool),
):
    """
    List newsletter subscribers (admin endpoint).
    """
    async with pool.acquire() as conn:
        # Build query with filters
        conditions = ["unsubscribed_at IS NULL"]
        params = []
        param_idx = 1

        if category:
            conditions.append(f"${param_idx} = ANY(categories)")
            params.append(category)
            param_idx += 1

        if frequency:
            conditions.append(f"frequency = ${param_idx}")
            params.append(frequency)
            param_idx += 1

        if confirmed is not None:
            conditions.append(f"confirmed = ${param_idx}")
            params.append(confirmed)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        params.extend([limit, offset])

        query = f"""
            SELECT id, email, name, categories, frequency, language, confirmed, created_at
            FROM newsletter_subscribers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        rows = await conn.fetch(query, *params)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM newsletter_subscribers WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params[:-2])

        subscribers = [
            SubscriberResponse(
                id=row["id"],
                email=row["email"],
                name=row["name"],
                categories=row["categories"] or [],
                frequency=row["frequency"] or "weekly",
                language=row["language"] or "en",
                confirmed=row["confirmed"] or False,
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return {
            "subscribers": [s.model_dump() for s in subscribers],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.post("/log")
async def log_newsletter_send(
    article_id: str,
    recipient_count: int,
    sent_count: int,
    failed_count: int,
    pool=Depends(get_database_pool),
):
    """
    Log a newsletter send event (admin endpoint).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO newsletter_send_log (article_id, recipient_count, sent_count, failed_count)
            VALUES ($1, $2, $3, $4)
            """,
            article_id,
            recipient_count,
            sent_count,
            failed_count,
        )

        return {"success": True}
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/routers/telegram.py:1003`

**Component:** backend

**Assignee:** @router

**Content:**
```
# TODO: Trigger publish to BaliZero API

            else:
                # Vote recorded, update tally
                approve_count = len(data["votes"]["approve"])
                await telegram_bot.answer_callback_query(
                    callback_id,
                    f"✅ Voto registrato ({approve_count}/{REQUIRED_VOTES})",
                    show_alert=False,
                )
                # Update message with new tally, keep buttons
                tally_text = format_vote_tally(data, original_text)
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=tally_text,
                    parse_mode=None,
                    reply_markup={
                        "inline_keyboard": [
                            [
                                {"text": "✅ APPROVE", "callback_data": f"approve:{article_id}"},
                                {"text": "❌ REJECT", "callback_data": f"reject:{article_id}"},
                            ],
                            [
                                {
                                    "text": "✏️ REQUEST CHANGES",
                                    "callback_data": f"changes:{article_id}",
                                }
                            ],
                        ]
                    },
                )

        # Handle REJECT vote
        elif action == "reject":
            data, result = add_vote(article_id, "reject", user)

            if result == "already_voted":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Hai già votato!", show_alert=True
                )

            elif result == "voting_closed":
                await telegram_bot.answer_callback_query(
                    callback_id, "⚠️ Votazione già chiusa", show_alert=True
                )

            elif result == "rejected":
                # Majority reached - REJECTED!
                voters = ", ".join([v["user_name"] for v in data["votes"]["reject"]])
                await telegram_bot.answer_callback_query(
                    callback_id, "❌ RIFIUTATO! Maggioranza raggiunta!", show_alert=True
                )
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ RIFIUTATO (2/3)\n\nArticolo {article_id}\n\nRifiutato da: {voters}\n\nL'articolo è stato scartato.",
                    parse_mode=None,
                )

            else:
                # Vote recorded, update tally
                reject_count = len(data["votes"]["reject"])
                await telegram_bot.answer_callback_query(
                    callback_id,
                    f"❌ Voto registrato ({reject_count}/{REQUIRED_VOTES})",
                    show_alert=False,
                )
                # Update message with new tally, keep buttons
                tally_text = format_vote_tally(data, original_text)
                await telegram_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=tally_text,
                    parse_mode=None,
                    reply_markup={
                        "inline_keyboard": [
                            [
                                {"text": "✅ APPROVE", "callback_data": f"approve:{article_id}"},
                                {"text": "❌ REJECT", "callback_data": f"reject:{article_id}"},
                            ],
                            [
                                {
                                    "text": "✏️ REQUEST CHANGES",
                                    "callback_data": f"changes:{article_id}",
                                }
                            ],
                        ]
                    },
                )

        # Handle REQUEST CHANGES
        elif action == "changes":
            data = get_article_status(article_id)
            if "feedback" not in data:
                data["feedback"] = []
            data["feedback"].append(
                {
                    "user_id": user.get("id"),
                    "user_name": user_name,
                    "requested_at": datetime.utcnow().isoformat(),
                }
            )
            save_article_status(article_id, data)

            await telegram_bot.answer_callback_query(
                callback_id, "✏️ Rispondi con il tuo feedback", show_alert=True
            )
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=f"✏️ {user_name} richiede modifiche\n\nRispondi a questo messaggio con le modifiche desiderate per l'articolo {article_id}.\n\nEsempio: Aggiungi più dettagli sulla procedura",
                parse_mode=None,
            )

        else:
            await telegram_bot.answer_callback_query(
                callback_id, f"Azione sconosciuta: {action}", show_alert=True
            )

        return {"ok": True}

    # Handle message
    message = update.message or update.edited_message
    if message:
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        message_id = message.get("message_id")
        user = message.get("from", {})
        user_name = user.get("first_name", "User")

        if chat_id and text:
            # Handle /start command
            if text.strip() == "/start":
                welcome_text = (
                    "👋 Hi! I'm Zantara, your AI assistant for visas, "
                    "business setup, and legal matters in Indonesia.\n\n"
                    "Ask me anything - I'll respond in your language! 🇮🇩\n\n"
                    "Powered by Bali Zero"
                )
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    # No parse_mode - use plain text to avoid Markdown parsing errors
                )
                return {"ok": True}

            # Handle /help command
            if text.strip() == "/help":
                help_text = (
                    "🆘 How can I help you:\n\n"
                    "• Visa questions (KITAS, KITAP, VOA, B211)\n"
                    "• PT PMA / company setup\n"
                    "• Indonesia tax matters\n"
                    "• Work permits (IMTA)\n"
                    "• Bali Zero pricing & procedures\n\n"
                    "Ask in any language - I'll adapt!"
                )
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=help_text,
                    # No parse_mode - use plain text to avoid Markdown parsing errors
                )
                return {"ok": True}

            # Process normal message in background
            background_tasks.add_task(
                process_telegram_message,
                chat_id=chat_id,
                message_text=text,
                user_name=user_name,
                message_id=message_id,
                request=request,
            )

    return {"ok": True}


@router.post("/setup-webhook")
async def setup_webhook(req: WebhookSetupRequest):
    """
    Set up Telegram webhook.

    If webhook_url is not provided, uses default Fly.io URL.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    # Default webhook URL
    webhook_url = req.webhook_url or "https://nuzantara-rag.fly.dev/api/telegram/webhook"

    try:
        result = await telegram_bot.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=["message", "edited_message", "callback_query"],
        )
        return {
            "success": True,
            "webhook_url": webhook_url,
            "telegram_response": result,
        }
    except Exception as e:
        logger.error(f"Failed to set up webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhook")
async def delete_webhook():
    """Remove Telegram webhook."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.delete_webhook()
        return {"success": True, "telegram_response": result}
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook-info")
async def get_webhook_info():
    """Get current webhook configuration."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.get_webhook_info()
        return result
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bot-info")
async def get_bot_info():
    """Get bot information."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    try:
        result = await telegram_bot.get_me()
        return result
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/app/utils/crm_utils.py:8`

**Component:** backend

**Assignee:** @balizero

**Content:**
```
# TODO: Move to database or environment variables in the future
CRM_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "admin@balizero.com",
    "admin@zantara.io",
}

# Super admins (by username prefix/email)
SUPER_ADMIN_EMAILS: set[str] = {
    "zero@balizero.com",
    "antonellosiano@gmail.com",
}

logger = logging.getLogger(__name__)


def is_crm_admin(user: dict) -> bool:
    """
    Check if a user has administrative access to the CRM.

    Admins can see all clients, all practices, and perform bulk actions.

    Args:
        user: User dictionary from authentication (get_current_user)

    Returns:
        bool: True if user is admin
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    role = user.get("role", "").lower()

    # Check by email or role
    result = email in CRM_ADMIN_EMAILS or role == "admin"

    if result:
        logger.debug(f"RBAC: User {email} granted CRM admin access (role={role})")

    return result


def is_super_admin(user: dict) -> bool:
    """
    Check if a user is a super admin (e.g. Zero).
    """
    if not user:
        return False

    email = user.get("email", "").lower()
    return email in SUPER_ADMIN_EMAILS
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/core/chunker.py:232`

**Component:** backend

**Content:**
```
# TODO: Implement page-aware chunking
        # For now, use semantic chunking
        return self.semantic_chunk(text, metadata)


def semantic_chunk(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """
    Convenience function for quick semantic chunking.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk (approximated as characters)
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    chunker = TextChunker(chunk_size=max_tokens, chunk_overlap=overlap)
    chunk_objects = chunker.semantic_chunk(text)
    return [chunk["text"] for chunk in chunk_objects]
```

---

### TODO - P3

**File:** `apps/backend-rag/backend/services/memory/collective_memory_workflow.py:61`

**Component:** backend

**Content:**
```
# TODO: Usare NER più sofisticato
    common_names = ["antonello", "maria", "giovanni", "luca", "sara"]
    found = []
    text_lower = text.lower()
    for name in common_names:
        if name in text_lower:
            found.append(name)
    return found


def merge_memories(existing: list[dict], new_content: str) -> dict:
    """Unifica memorie esistenti con nuovo contenuto"""
    if not existing:
        return {"content": new_content}

    # Prendi la memoria più recente come base
    latest = existing[0]
    return {
        "content": f"{latest.get('content', '')}\n{new_content}",
        "memory_key": latest.get("memory_key"),
        "updated": True,
    }


def detect_conflicts(_existing: list[dict], _new_content: str) -> list[str]:
    """Rileva conflitti tra memorie esistenti e nuovo contenuto"""
    conflicts = []
    # TODO: Implementare logica di rilevamento conflitti
    return conflicts


def extract_preferences(text: str) -> dict[str, str]:
    """Estrae preferenze dal testo"""
    preferences = {}
    text_lower = text.lower()

    # Pattern matching semplice
    if "preferisce" in text_lower or "preferisco" in text_lower:
        if "espresso" in text_lower:
            preferences["coffee"] = "espresso"
        if "americano" in text_lower:
            preferences["coffee"] = "americano"

    return preferences


async def analyze_content_intent(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Analizza intent e categoria della memoria"""
    query = state["query"].lower()

    # Rileva categoria
    if any(word in query for word in ["preferisco", "mi piace", "non mi piace", "amo", "odio"]):
        state["detected_category"] = MemoryCategory.PREFERENCE
    elif any(word in query for word in ["compleanno", "anniversario", "festa", "celebrazione"]):
        state["detected_category"] = MemoryCategory.MILESTONE
    elif any(
        word in query
        for word in ["amicizia", "conosco", "incontri", "incontrato", "social", "amico"]
    ):
        state["detected_category"] = MemoryCategory.RELATIONSHIP
    elif any(word in query for word in ["cultura", "tradizione", "costume", "locale"]):
        state["detected_category"] = MemoryCategory.CULTURAL
    else:
        state["detected_category"] = MemoryCategory.WORK

    # Rileva tipo
    if state["detected_category"] == MemoryCategory.PREFERENCE:
        state["detected_type"] = "preference"
    elif state["detected_category"] == MemoryCategory.MILESTONE:
        state["detected_type"] = "milestone"
    else:
        state["detected_type"] = "fact"

    return state


async def extract_entities_and_relationships(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Estrae entità e relazioni"""
    query = state["query"]

    # Estrai nomi di persone
    participants = extract_person_names(query)
    if not participants and state.get("user_id"):
        participants = [state["user_id"]]

    state["participants"] = participants
    state["extracted_entities"] = []  # TODO: Integrare con MCP Memory

    return state


async def check_existing_memories(
    state: CollectiveMemoryState, _memory_service
) -> CollectiveMemoryState:
    """Verifica memorie esistenti correlate"""
    # Cerca memorie simili (semplificato)
    # TODO: Implementare ricerca semantica nel database
    state["existing_memories"] = []
    state["needs_consolidation"] = False

    return state


async def categorize_memory(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Categorizza memoria (già fatto in analyze_content_intent)"""
    return state


async def assess_personal_importance(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Valuta importanza personale (non solo lavorativa)"""
    category = state["detected_category"]
    len(state["participants"])

    # Calcola importanza basata su categoria
    if category == MemoryCategory.MILESTONE:
        importance = 0.9
    elif category == MemoryCategory.RELATIONSHIP:
        importance = 0.8
    elif category == MemoryCategory.PREFERENCE:
        importance = 0.6
    else:
        importance = 0.5

    state["importance_score"] = importance
    state["personal_importance"] = importance * 1.2  # Boost per importanza personale

    return state


async def consolidate_with_existing(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Consolida con memorie esistenti"""
    existing = state["existing_memories"]
    new_content = state["query"]

    if existing:
        consolidated = merge_memories(existing, new_content)
        conflicts = detect_conflicts(existing, new_content)

        if conflicts:
            state["consolidation_actions"].append(f"Conflict detected: {conflicts}")

        state["memory_to_store"] = consolidated
    else:
        state["memory_to_store"] = {"content": new_content}

    return state


async def update_team_relationships(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Aggiorna relazioni tra membri del team"""
    participants = state["participants"]
    category = state["detected_category"]

    if len(participants) >= 2 and category in [
        MemoryCategory.RELATIONSHIP,
        MemoryCategory.MILESTONE,
    ]:
        for i, member_a in enumerate(participants):
            for member_b in participants[i + 1 :]:
                relationship = {
                    "member_a": member_a,
                    "member_b": member_b,
                    "relationship_type": (
                        "friendship" if category == MemoryCategory.RELATIONSHIP else "social"
                    ),
                    "last_interaction": datetime.now().isoformat(),
                }
                state["relationships_to_update"].append(relationship)

    return state


async def update_member_profiles(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Aggiorna profili personali dei membri"""
    if state["detected_category"] == MemoryCategory.PREFERENCE:
        preferences = extract_preferences(state["query"])
        for participant in state["participants"]:
            state["profile_updates"].append({"member_id": participant, "preferences": preferences})

    return state


async def store_collective_memory(
    state: CollectiveMemoryState, memory_service
) -> CollectiveMemoryState:
    """Salva memoria collettiva"""
    if state["memory_to_store"] and memory_service:
        try:
            content = state["memory_to_store"].get("content")
            user_id = state.get("user_id")

            if content and user_id:
                # Save as fact
                await memory_service.add_fact(user_id, content, fact_type="collective_memory")
                logger.info(f"💾 Stored collective memory fact for {user_id}: {content}")

                # Also update summary if needed (simplified logic)
                # In a real scenario, we'd append to summary or re-summarize
                # await memory_service.update_summary(user_id, content)

        except Exception as e:
            logger.error(f"❌ Failed to store collective memory: {e}")
            # Add error to state for tracking
            if "errors" not in state:
                state["errors"] = []
            state["errors"].append(str(e))

    return state


def route_by_existence(state: CollectiveMemoryState) -> str:
    """Routing basato su esistenza memorie"""
    if state["needs_consolidation"]:
        return "consolidate"
    elif state["existing_memories"]:
        return "exists"
    else:
        return "new"


def route_by_importance(state: CollectiveMemoryState) -> str:
    """Routing basato su importanza"""
    if state["personal_importance"] >= 0.8:
        return "high"
    elif state["personal_importance"] >= 0.6:
        return "medium"
    else:
        return "low"


def create_collective_memory_workflow(memory_service=None, _mcp_client=None):
    """Crea workflow LangGraph per memoria collettiva intelligente"""

    workflow = StateGraph(CollectiveMemoryState)

    # Wrappers for dependency injection
    async def check_existing_wrapper(state):
        return await check_existing_memories(state, memory_service)

    async def store_memory_wrapper(state):
        return await store_collective_memory(state, memory_service)

    # NODES
    workflow.add_node("analyze_content", analyze_content_intent)
    workflow.add_node("extract_entities", extract_entities_and_relationships)
    workflow.add_node("check_existing", check_existing_wrapper)
    workflow.add_node("categorize", categorize_memory)
    workflow.add_node("assess_importance", assess_personal_importance)
    workflow.add_node("consolidate", consolidate_with_existing)
    workflow.add_node("update_relationships", update_team_relationships)
    workflow.add_node("update_profiles", update_member_profiles)
    workflow.add_node("store_memory", store_memory_wrapper)

    # FLOW
    workflow.set_entry_point("analyze_content")

    workflow.add_edge("analyze_content", "extract_entities")
    workflow.add_edge("extract_entities", "check_existing")

    workflow.add_conditional_edges(
        "check_existing",
        route_by_existence,
        {"new": "categorize", "exists": "consolidate", "consolidate": "consolidate"},
    )

    workflow.add_edge("categorize", "assess_importance")
    workflow.add_edge("consolidate", "assess_importance")
    workflow.add_edge("assess_importance", "update_relationships")

    workflow.add_conditional_edges(
        "update_relationships",
        route_by_importance,
        {"high": "update_profiles", "medium": "store_memory", "low": "store_memory"},
    )

    workflow.add_edge("update_profiles", "store_memory")
    workflow.add_edge("store_memory", END)

    return workflow.compile()
```

---

... and 26 more items

---

## 💡 Recommendations

👥 **22 items are unassigned** - Consider assigning ownership
🔗 **35 items lack GitHub issues** - Create issues for better tracking