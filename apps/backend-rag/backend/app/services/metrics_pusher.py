"""
Grafana Cloud Metrics Pusher

Pushes Prometheus metrics to Grafana Cloud using the remote_write API.
This enables metrics visualization in Grafana Cloud dashboards.

Author: ZANTARA Development Team
Date: 2026-01-01
"""

import asyncio
import base64
import logging
import re
import struct
import time
from typing import Any

import httpx

logger = logging.getLogger("zantara.metrics_pusher")


class MetricsPusher:
    """
    Pushes Prometheus metrics to Grafana Cloud.

    Uses the Prometheus remote_write protocol with snappy compression.
    Runs as a background task, pushing metrics at configurable intervals.
    """

    def __init__(
        self,
        remote_write_url: str,
        username: str,
        token: str,
        push_interval: int = 15,
        service_name: str = "nuzantara-backend",
    ):
        """
        Initialize the metrics pusher.

        Args:
            remote_write_url: Grafana Cloud Prometheus remote write URL
            username: Grafana Cloud instance ID
            token: Grafana Cloud API token
            push_interval: Seconds between metric pushes
            service_name: Service name label for all metrics
        """
        self.remote_write_url = remote_write_url
        self.username = username
        self.token = token
        self.push_interval = push_interval
        self.service_name = service_name
        self._running = False
        self._task: asyncio.Task | None = None

        # Create basic auth header
        auth_string = f"{username}:{token}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        self.auth_header = f"Basic {auth_bytes}"

        logger.info(f"MetricsPusher initialized for {remote_write_url}")

    def _parse_prometheus_text(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Prometheus text format into structured metrics.

        Args:
            text: Prometheus exposition format text

        Returns:
            List of metric dictionaries with name, labels, value, timestamp
        """
        metrics = []
        current_time_ms = int(time.time() * 1000)

        for line in text.split('\n'):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            try:
                # Parse metric line: name{labels} value [timestamp]
                # Handle metrics with and without labels
                if '{' in line:
                    match = re.match(r'([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9.eE+-]+)', line)
                    if match:
                        name = match.group(1)
                        labels_str = match.group(2)
                        value = float(match.group(3))

                        # Parse labels
                        labels = {"__name__": name, "service": self.service_name}
                        if labels_str:
                            for label in re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', labels_str):
                                labels[label[0]] = label[1]

                        metrics.append({
                            "name": name,
                            "labels": labels,
                            "value": value,
                            "timestamp": current_time_ms,
                        })
                else:
                    # Metric without labels
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        value = float(parts[1])

                        metrics.append({
                            "name": name,
                            "labels": {"__name__": name, "service": self.service_name},
                            "value": value,
                            "timestamp": current_time_ms,
                        })
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse metric line: {line} - {e}")
                continue

        return metrics

    def _encode_varint(self, value: int) -> bytes:
        """Encode an integer as a protobuf varint."""
        result = []
        while value > 127:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value)
        return bytes(result)

    def _encode_string(self, field_number: int, value: str) -> bytes:
        """Encode a string field in protobuf format."""
        tag = (field_number << 3) | 2  # Wire type 2 = length-delimited
        encoded_value = value.encode('utf-8')
        return self._encode_varint(tag) + self._encode_varint(len(encoded_value)) + encoded_value

    def _encode_label(self, name: str, value: str) -> bytes:
        """Encode a Label message (name=1, value=2)."""
        content = self._encode_string(1, name) + self._encode_string(2, value)
        return content

    def _encode_sample(self, value: float, timestamp: int) -> bytes:
        """Encode a Sample message (value=1, timestamp=2)."""
        # value is double (wire type 1), timestamp is int64 (wire type 0)
        value_bytes = (1 << 3 | 1).to_bytes(1, 'little') + struct.pack('<d', value)
        timestamp_bytes = self._encode_varint((2 << 3) | 0) + self._encode_varint(timestamp)
        return value_bytes + timestamp_bytes

    def _encode_timeseries(self, metric: dict) -> bytes:
        """Encode a TimeSeries message."""
        content = b''

        # Encode labels (field 1, repeated)
        for label_name, label_value in metric["labels"].items():
            label_content = self._encode_label(label_name, str(label_value))
            content += self._encode_varint((1 << 3) | 2) + self._encode_varint(len(label_content)) + label_content

        # Encode sample (field 2)
        sample_content = self._encode_sample(metric["value"], metric["timestamp"])
        content += self._encode_varint((2 << 3) | 2) + self._encode_varint(len(sample_content)) + sample_content

        return content

    def _encode_write_request(self, metrics: list[dict]) -> bytes:
        """
        Encode metrics as a Prometheus WriteRequest protobuf message.

        Note: This is a simplified encoder. For production, consider using
        the official protobuf definitions.
        """
        content = b''

        for metric in metrics:
            ts_content = self._encode_timeseries(metric)
            # timeseries is field 1
            content += self._encode_varint((1 << 3) | 2) + self._encode_varint(len(ts_content)) + ts_content

        return content

    def _snappy_compress(self, data: bytes) -> bytes:
        """
        Compress data using snappy framing format.
        Falls back to uncompressed if snappy not available.
        """
        try:
            import snappy
            return snappy.compress(data)
        except ImportError:
            logger.warning("snappy not installed, sending uncompressed metrics")
            return data

    async def _collect_metrics(self) -> str:
        """Collect current metrics from prometheus_client."""
        try:
            from prometheus_client import generate_latest, REGISTRY
            return generate_latest(REGISTRY).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return ""

    async def _push_metrics(self) -> bool:
        """
        Push current metrics to Grafana Cloud.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Collect metrics
            metrics_text = await self._collect_metrics()
            if not metrics_text:
                logger.debug("No metrics to push")
                return True

            # Parse into structured format
            metrics = self._parse_prometheus_text(metrics_text)
            if not metrics:
                logger.debug("No metrics parsed")
                return True

            # Encode as protobuf
            write_request = self._encode_write_request(metrics)

            # Compress with snappy
            compressed = self._snappy_compress(write_request)

            # Push to Grafana Cloud
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.remote_write_url,
                    content=compressed,
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/x-protobuf",
                        "Content-Encoding": "snappy",
                        "X-Prometheus-Remote-Write-Version": "0.1.0",
                    },
                )

                if response.status_code in (200, 204):
                    logger.debug(f"Pushed {len(metrics)} metrics to Grafana Cloud")
                    return True
                else:
                    logger.warning(
                        f"Failed to push metrics: {response.status_code} - {response.text[:200]}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error pushing metrics: {e}")
            return False

    async def _run_loop(self):
        """Background loop that pushes metrics periodically."""
        logger.info(f"Starting metrics push loop (interval: {self.push_interval}s)")
        # #region agent log
        import json
        with open('/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"metrics_pusher.py:261","message":"MetricsPusher loop entered","data":{"running":self._running,"push_interval":self.push_interval}},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion

        while self._running:
            # #region agent log
            with open('/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"metrics_pusher.py:262","message":"MetricsPusher loop iteration","data":{"running":self._running}},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            # #endregion
            try:
                await self._push_metrics()
            except Exception as e:
                logger.error(f"Error in metrics push loop: {e}")

            await asyncio.sleep(self.push_interval)

        logger.info("Metrics push loop stopped")

    def start(self):
        """Start the background metrics push task."""
        if self._running:
            logger.warning("MetricsPusher already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("MetricsPusher started")

    async def stop(self):
        """Stop the background metrics push task."""
        # #region agent log
        import json
        with open('/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"metrics_pusher.py:290","message":"MetricsPusher stop called","data":{"running_before":self._running,"has_task":self._task is not None}},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # #region agent log
        with open('/Users/antonellosiano/Desktop/nuzantara/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"metrics_pusher.py:303","message":"MetricsPusher stop completed","data":{"running_after":self._running}},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion

        logger.info("MetricsPusher stopped")

    async def health_check(self) -> dict[str, Any]:
        """Check if metrics pusher is healthy."""
        return {
            "status": "running" if self._running else "stopped",
            "remote_write_url": self.remote_write_url,
            "push_interval": self.push_interval,
        }


# Global instance
_metrics_pusher: MetricsPusher | None = None


def get_metrics_pusher() -> MetricsPusher | None:
    """Get the global metrics pusher instance."""
    return _metrics_pusher


def init_metrics_pusher(
    remote_write_url: str,
    username: str,
    token: str,
    push_interval: int = 15,
    service_name: str = "nuzantara-backend",
) -> MetricsPusher:
    """
    Initialize and start the global metrics pusher.

    Args:
        remote_write_url: Grafana Cloud Prometheus remote write URL
        username: Grafana Cloud instance ID
        token: Grafana Cloud API token
        push_interval: Seconds between metric pushes
        service_name: Service name label for all metrics

    Returns:
        MetricsPusher instance
    """
    global _metrics_pusher

    if _metrics_pusher is not None:
        logger.warning("MetricsPusher already initialized")
        return _metrics_pusher

    _metrics_pusher = MetricsPusher(
        remote_write_url=remote_write_url,
        username=username,
        token=token,
        push_interval=push_interval,
        service_name=service_name,
    )
    _metrics_pusher.start()

    return _metrics_pusher


async def shutdown_metrics_pusher():
    """Shutdown the global metrics pusher."""
    global _metrics_pusher

    if _metrics_pusher is not None:
        await _metrics_pusher.stop()
        _metrics_pusher = None
