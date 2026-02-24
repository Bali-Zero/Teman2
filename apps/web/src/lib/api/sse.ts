/**
 * SSE stream parser — converts a ReadableStream into StreamNodeEvent objects.
 *
 * Handles the text/event-stream format:
 *   event: node_start
 *   data: {"run_id":"...","event_type":"node_start",...}
 *   id: abc-0
 *
 * Lines are separated by \n, events by \n\n.
 */

import type { StreamNodeEvent } from "@nuzantara/ts-schemas";

export async function* parseSSEStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamNodeEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split on double newline (SSE event boundary)
      const parts = buffer.split("\n\n");
      // Keep the last incomplete part in the buffer
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const event = parseSSEEvent(part);
        if (event) {
          yield event;
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      const event = parseSSEEvent(buffer);
      if (event) {
        yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSSEEvent(raw: string): StreamNodeEvent | null {
  const lines = raw.split("\n");
  let data: string | null = null;

  for (const line of lines) {
    // Skip comments (keepalive)
    if (line.startsWith(":")) continue;

    if (line.startsWith("data: ")) {
      data = line.slice(6);
    } else if (line.startsWith("data:")) {
      data = line.slice(5);
    }
  }

  if (!data) return null;

  try {
    return JSON.parse(data) as StreamNodeEvent;
  } catch {
    return null;
  }
}
