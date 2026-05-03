/**
 * Frontend Metrics System
 *
 * Collects metrics from React hooks and components for monitoring.
 * Metrics can be sent to backend for Prometheus integration.
 */

export interface MetricLabels {
  [key: string]: string | number;
}

export interface MetricValue {
  name: string;
  value: number;
  labels?: MetricLabels;
  timestamp: number;
}

class MetricsCollector {
  private metrics: MetricValue[] = [];
  private maxMetrics = 1000;
  private flushInterval: number | null = null;

  constructor() {
    // Auto-flush metrics every 30 seconds
    if (typeof window !== "undefined") {
      this.flushInterval = window.setInterval(() => {
        this.flush();
      }, 30000);
    }
  }

  /**
   * Increment a counter metric
   */
  increment(name: string, labels?: MetricLabels): void {
    this.addMetric({
      name: `zantara_frontend_${name}_total`,
      value: 1,
      labels,
      timestamp: Date.now(),
    });
  }

  /**
   * Set a gauge metric
   */
  gauge(name: string, value: number, labels?: MetricLabels): void {
    this.addMetric({
      name: `zantara_frontend_${name}`,
      value,
      labels,
      timestamp: Date.now(),
    });
  }

  /**
   * Record a histogram value
   */
  histogram(name: string, value: number, labels?: MetricLabels): void {
    this.addMetric({
      name: `zantara_frontend_${name}_seconds`,
      value,
      labels,
      timestamp: Date.now(),
    });
  }

  /**
   * Add a metric to the collection
   */
  private addMetric(metric: MetricValue): void {
    this.metrics.push(metric);
    if (this.metrics.length > this.maxMetrics) {
      this.metrics.shift();
    }
  }

  /**
   * Get all metrics
   */
  getMetrics(): MetricValue[] {
    return [...this.metrics];
  }

  /**
   * Clear metrics
   */
  clear(): void {
    this.metrics = [];
  }

  /**
   * Flush metrics to backend
   * NOTE: Endpoint not yet implemented, silently skip
   */
  async flush(): Promise<void> {
    if (this.metrics.length === 0) return;

    const metricsToSend = [...this.metrics];
    this.metrics = [];

    // TODO: Enable when backend endpoint /api/metrics/frontend is implemented
    // Currently the endpoint returns 404, so we skip the network call
    // Metrics are still collected locally and available via getMetrics()
    return;
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
      this.flushInterval = null;
    }
    this.flush();
  }
}

export const metrics = new MetricsCollector();

// Chat-specific metrics helpers
export const chatMetrics = {
  messageSent: (hasImages: boolean, imageCount: number) => {
    metrics.increment("chat_message_sent_total", {
      has_images: hasImages ? "true" : "false",
      image_count: imageCount,
    });
  },

  messageReceived: (responseLength: number, executionTime: number) => {
    metrics.increment("chat_message_received_total");
    metrics.histogram("chat_message_execution_time", executionTime);
    metrics.gauge("chat_message_response_length", responseLength);
  },

  ttsStarted: (messageId: string) => {
    metrics.increment("chat_tts_started_total", { message_id: messageId });
  },

  ttsCompleted: (messageId: string, duration: number) => {
    metrics.increment("chat_tts_completed_total", { message_id: messageId });
    metrics.histogram("chat_tts_duration", duration);
  },

  ttsError: (messageId: string, errorType: string) => {
    metrics.increment("chat_tts_errors_total", {
      message_id: messageId,
      error_type: errorType,
    });
  },

  imageAttached: (imageCount: number, totalSize: number) => {
    metrics.increment("chat_image_attached_total", { image_count: imageCount });
    metrics.gauge("chat_image_total_size_bytes", totalSize);
  },

  audioTranscribed: (
    blobSize: number,
    textLength: number,
    duration: number,
  ) => {
    metrics.increment("chat_audio_transcribed_total");
    metrics.histogram("chat_audio_transcription_duration", duration);
    metrics.gauge("chat_audio_blob_size_bytes", blobSize);
    metrics.gauge("chat_audio_transcription_length", textLength);
  },

  sidebarOpened: () => {
    metrics.increment("chat_sidebar_opened_total");
  },

  sidebarClosed: () => {
    metrics.increment("chat_sidebar_closed_total");
  },

  conversationLoaded: (conversationId: number, messageCount: number) => {
    metrics.increment("chat_conversation_loaded_total", {
      conversation_id: String(conversationId),
    });
    metrics.gauge("chat_conversation_message_count", messageCount, {
      conversation_id: String(conversationId),
    });
  },

  conversationSaved: (sessionId: string, messageCount: number) => {
    metrics.increment("chat_conversation_saved_total", {
      session_id: sessionId,
    });
    metrics.gauge("chat_conversation_saved_message_count", messageCount);
  },

  streamingStarted: (sessionId: string) => {
    metrics.increment("chat_streaming_started_total", {
      session_id: sessionId,
    });
  },

  streamingCompleted: (sessionId: string, duration: number) => {
    metrics.increment("chat_streaming_completed_total", {
      session_id: sessionId,
    });
    metrics.histogram("chat_streaming_duration", duration);
  },

  streamingError: (sessionId: string, errorType: string) => {
    metrics.increment("chat_streaming_errors_total", {
      session_id: sessionId,
      error_type: errorType,
    });
  },
};

// Cleanup on page unload
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    metrics.flush();
  });
}
