import { describe, it, expect } from "vitest";
import { parseSSEStream } from "@/lib/api/sse";

function makeStream(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

describe("parseSSEStream", () => {
  it("parses a single event", async () => {
    const stream = makeStream(
      'event: node_start\ndata: {"run_id":"r1","event_type":"node_start","node":"understand","data":{},"sequence":0}\nid: r1-0\n\n',
    );

    const events = [];
    for await (const event of parseSSEStream(stream)) {
      events.push(event);
    }

    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe("node_start");
    expect(events[0].node).toBe("understand");
    expect(events[0].run_id).toBe("r1");
  });

  it("parses multiple events", async () => {
    const stream = makeStream(
      'event: node_start\ndata: {"run_id":"r1","event_type":"node_start","node":"understand","data":{},"sequence":0}\n\n' +
        'event: node_end\ndata: {"run_id":"r1","event_type":"node_end","node":"understand","data":{"intent":"general"},"sequence":1}\n\n' +
        'event: done\ndata: {"run_id":"r1","event_type":"done","node":"pipeline","data":{},"sequence":2}\n\n',
    );

    const events = [];
    for await (const event of parseSSEStream(stream)) {
      events.push(event);
    }

    expect(events).toHaveLength(3);
    expect(events[0].event_type).toBe("node_start");
    expect(events[1].event_type).toBe("node_end");
    expect(events[1].data.intent).toBe("general");
    expect(events[2].event_type).toBe("done");
  });

  it("skips keepalive comments", async () => {
    const stream = makeStream(
      ": keepalive\n\n" +
        'event: done\ndata: {"run_id":"r1","event_type":"done","node":"pipeline","data":{},"sequence":0}\n\n',
    );

    const events = [];
    for await (const event of parseSSEStream(stream)) {
      events.push(event);
    }

    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe("done");
  });

  it("handles chunked delivery", async () => {
    const encoder = new TextEncoder();
    const full =
      'event: node_start\ndata: {"run_id":"r1","event_type":"node_start","node":"retrieve","data":{},"sequence":0}\n\n';

    // Split in the middle
    const mid = Math.floor(full.length / 2);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(full.slice(0, mid)));
        controller.enqueue(encoder.encode(full.slice(mid)));
        controller.close();
      },
    });

    const events = [];
    for await (const event of parseSSEStream(stream)) {
      events.push(event);
    }

    expect(events).toHaveLength(1);
    expect(events[0].node).toBe("retrieve");
  });

  it("skips invalid JSON gracefully", async () => {
    const stream = makeStream(
      "event: bad\ndata: not-json\n\n" +
        'event: good\ndata: {"run_id":"r1","event_type":"done","node":"pipeline","data":{},"sequence":0}\n\n',
    );

    const events = [];
    for await (const event of parseSSEStream(stream)) {
      events.push(event);
    }

    expect(events).toHaveLength(1);
    expect(events[0].event_type).toBe("done");
  });
});
