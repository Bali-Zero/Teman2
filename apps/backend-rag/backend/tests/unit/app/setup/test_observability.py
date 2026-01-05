"""
Unit tests for Observability Setup
Target: >99% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.observability import setup_observability


class TestObservabilitySetup:
    """Tests for observability setup"""

    @patch("app.setup.observability.Instrumentator")
    def test_setup_observability_basic(self, mock_instrumentator):
        """Test basic observability setup (Prometheus only)"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.otel_enabled = False

            setup_observability(mock_app)

            mock_instrumentator.assert_called_once()
            mock_instrumentator_instance.instrument.assert_called_once_with(mock_app)
            mock_instrumentator_instance.expose.assert_called_once_with(mock_app)

    @patch("app.setup.observability.Instrumentator")
    @patch("app.setup.observability.trace")
    @patch("app.setup.observability.Resource")
    @patch("app.setup.observability.TracerProvider")
    @patch("app.setup.observability.BatchSpanProcessor")
    @patch("app.setup.observability.OTLPGrpcSpanExporter")
    def test_setup_observability_with_otel_grpc(
        self,
        mock_grpc_exporter,
        mock_batch_processor,
        mock_tracer_provider,
        mock_resource,
        mock_trace,
        mock_instrumentator,
    ):
        """Test observability setup with OpenTelemetry gRPC (local Jaeger)"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", True):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.otel_enabled = True
                mock_settings.otel_service_name = "test-service"
                mock_settings.environment = "test"
                mock_settings.otel_exporter_endpoint = "http://localhost:4317"
                mock_settings.otel_exporter_headers = None  # No headers = gRPC mode

                mock_tracer_provider_instance = MagicMock()
                mock_tracer_provider.return_value = mock_tracer_provider_instance
                mock_trace.get_tracer_provider.return_value = MagicMock()
                mock_grpc_exporter_instance = MagicMock()
                mock_grpc_exporter.return_value = mock_grpc_exporter_instance
                mock_batch_processor_instance = MagicMock()
                mock_batch_processor.return_value = mock_batch_processor_instance

                setup_observability(mock_app)

                mock_resource.create.assert_called_once()
                mock_trace.set_tracer_provider.assert_called_once()
                mock_grpc_exporter.assert_called_once_with(
                    endpoint="http://localhost:4317", insecure=True
                )
                mock_batch_processor.assert_called_once()
                mock_trace.get_tracer_provider.return_value.add_span_processor.assert_called_once()

    @patch("app.setup.observability.Instrumentator")
    @patch("app.setup.observability.trace")
    @patch("app.setup.observability.Resource")
    @patch("app.setup.observability.TracerProvider")
    @patch("app.setup.observability.BatchSpanProcessor")
    @patch("app.setup.observability.OTLPHttpSpanExporter")
    def test_setup_observability_with_otel_http(
        self,
        mock_http_exporter,
        mock_batch_processor,
        mock_tracer_provider,
        mock_resource,
        mock_trace,
        mock_instrumentator,
    ):
        """Test observability setup with OpenTelemetry HTTP (Grafana Cloud)"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", True):
            with patch("app.setup.observability.OTEL_HTTP_AVAILABLE", True):
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.otel_enabled = True
                    mock_settings.otel_service_name = "test-service"
                    mock_settings.environment = "test"
                    mock_settings.otel_exporter_endpoint = "https://otel-collector.grafana.net"
                    mock_settings.otel_exporter_headers = (
                        "Authorization=Basic token123"  # Headers = HTTP mode
                    )

                    mock_tracer_provider_instance = MagicMock()
                    mock_tracer_provider.return_value = mock_tracer_provider_instance
                    mock_trace.get_tracer_provider.return_value = MagicMock()
                    mock_http_exporter_instance = MagicMock()
                    mock_http_exporter.return_value = mock_http_exporter_instance
                    mock_batch_processor_instance = MagicMock()
                    mock_batch_processor.return_value = mock_batch_processor_instance

                    setup_observability(mock_app)

                    mock_resource.create.assert_called_once()
                    mock_trace.set_tracer_provider.assert_called_once()
                    mock_http_exporter.assert_called_once_with(
                        endpoint="https://otel-collector.grafana.net/v1/traces",
                        headers={"Authorization": "Basic token123"},
                    )
                    mock_batch_processor.assert_called_once()
                    mock_trace.get_tracer_provider.return_value.add_span_processor.assert_called_once()

    @patch("app.setup.observability.Instrumentator")
    @patch("app.setup.observability.OTLPHttpSpanExporter")
    def test_setup_observability_http_exporter_not_available(
        self, mock_http_exporter, mock_instrumentator
    ):
        """Test observability setup when HTTP exporter is not available"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", True):
            with patch("app.setup.observability.OTEL_HTTP_AVAILABLE", False):
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.otel_enabled = True
                    mock_settings.otel_exporter_headers = "Authorization=Basic token123"

                    setup_observability(mock_app)

                    # Should not call HTTP exporter if not available
                    mock_http_exporter.assert_not_called()

    @patch("app.setup.observability.Instrumentator")
    def test_setup_observability_otel_enabled_but_not_available(self, mock_instrumentator):
        """Test observability setup when OTEL is enabled but packages not installed"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", False):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.otel_enabled = True

                setup_observability(mock_app)

                # Should only setup Prometheus
                mock_instrumentator.assert_called_once()

    @patch("app.setup.observability.Instrumentator")
    @patch("app.setup.observability.trace")
    @patch("app.setup.observability.Resource")
    @patch("app.setup.observability.TracerProvider")
    @patch("app.setup.observability.BatchSpanProcessor")
    @patch("app.setup.observability.OTLPGrpcSpanExporter")
    def test_setup_observability_otel_exception(
        self,
        mock_grpc_exporter,
        mock_batch_processor,
        mock_tracer_provider,
        mock_resource,
        mock_trace,
        mock_instrumentator,
    ):
        """Test observability setup when OpenTelemetry setup raises exception"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", True):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.otel_enabled = True
                mock_settings.otel_service_name = "test-service"
                mock_settings.environment = "test"
                mock_settings.otel_exporter_endpoint = "http://localhost:4317"
                mock_settings.otel_exporter_headers = None

                mock_trace.set_tracer_provider.side_effect = Exception("OTEL setup failed")

                # Should not raise, just log warning
                setup_observability(mock_app)

                # Prometheus should still be set up
                mock_instrumentator.assert_called_once()

    @patch("app.setup.observability.Instrumentator")
    @patch("app.setup.observability.OTLPHttpSpanExporter")
    def test_setup_observability_http_headers_parsing(
        self, mock_http_exporter, mock_instrumentator
    ):
        """Test parsing of multiple HTTP headers"""
        mock_app = MagicMock()
        mock_instrumentator_instance = MagicMock()
        mock_instrumentator.return_value = mock_instrumentator_instance

        with patch("app.setup.observability.OTEL_AVAILABLE", True):
            with patch("app.setup.observability.OTEL_HTTP_AVAILABLE", True):
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.otel_enabled = True
                    mock_settings.otel_service_name = "test-service"
                    mock_settings.environment = "test"
                    mock_settings.otel_exporter_endpoint = "https://otel-collector.grafana.net"
                    mock_settings.otel_exporter_headers = (
                        "Authorization=Basic token123, X-Custom-Header=custom-value"
                    )

                    mock_trace.get_tracer_provider.return_value = MagicMock()
                    mock_http_exporter_instance = MagicMock()
                    mock_http_exporter.return_value = mock_http_exporter_instance

                    setup_observability(mock_app)

                    # Verify headers were parsed correctly
                    mock_http_exporter.assert_called_once()
                    call_kwargs = mock_http_exporter.call_args[1]
                    assert call_kwargs["headers"]["Authorization"] == "Basic token123"
                    assert call_kwargs["headers"]["X-Custom-Header"] == "custom-value"

