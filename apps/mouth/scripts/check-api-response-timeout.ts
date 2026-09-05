/** Loopback-only proof: real fetch, HTTP server, API facade and CRM consumer. */
import assert from "node:assert/strict";
import { once } from "node:events";
import { createServer } from "node:http";
import { setTimeout as delay } from "node:timers/promises";
import { ApiClient } from "../src/lib/api/api-client";
import { ApiClientBase } from "../src/lib/api/client";
import { ApiError } from "../src/lib/api/error-handler";

/** Independent review attack, preserved as a reproducible command. */
async function adversarial(): Promise<void> {
  const closed = new Set<string>();
  const server = createServer((request, response) => {
    const path = request.url!;
    response.on("close", () => closed.add(path));
    response.setHeader("Content-Type", "application/json");
    if (path === "/fast") {
      response.write("[");
      setTimeout(() => response.end("]"), 20);
    } else if (path === "/truncated") {
      response.write("[");
      setTimeout(() => response.destroy(), 30);
    } else if (path === "/malformed-error") {
      response.writeHead(503).end("invalid-json");
    } else {
      response.writeHead(path === "/stalled-error" ? 503 : 200);
      response.flushHeaders();
      response.write("[");
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address === "object");
  const api = new ApiClientBase(`http://127.0.0.1:${address.port}`);
  const watchdog = new AbortController();
  try {
    const results = await Promise.race([
      Promise.allSettled([
        api.request("/fast", {}, 1_000),
        api.request("/stall", {}, 200),
        api.request("/truncated", {}, 1_000),
        api.request("/malformed-error", {}, 1_000),
        api.request("/stalled-error", {}, 250),
      ]),
      delay(2_000, undefined, { signal: watchdog.signal }).then(() => {
        throw new Error("Concurrent requests did not settle");
      }),
    ]);
    assert.equal(results[0].status, "fulfilled");
    assert.deepEqual(results[0].value, []);
    assert.equal(results[1].status, "rejected");
    assert.equal(results[1].reason.message, "Request timeout");
    assert.equal(results[2].status, "rejected");
    assert.equal(results[2].reason.name, "TypeError");
    assert.notEqual(results[2].reason.message, "Request timeout");
    for (const result of results.slice(3)) {
      assert.equal(result.status, "rejected");
      assert(result.reason instanceof ApiError);
      assert.equal(result.reason.statusCode, 503);
    }
    for (
      let attempt = 0;
      attempt < 50 && !closed.has("/stalled-error");
      attempt++
    ) {
      await delay(10);
    }
    assert(closed.has("/stall") && closed.has("/stalled-error"));
    process.stdout.write(
      "Adversarial PASS: concurrency, truncated socket, HTTP errors, socket cleanup\n",
    );
  } finally {
    watchdog.abort();
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

async function main(): Promise<void> {
  const consumerMode = process.argv.includes("--consumer-default");
  const requests: string[] = [];
  let bodyStarted = false;
  let connectionClosed = false;
  const server = createServer((request, response) => {
    requests.push(`${request.method} ${request.url}`);
    if (request.url === "/empty") {
      response.writeHead(204).end();
      return;
    }
    response.setHeader("Content-Type", "application/json");
    if (request.url === "/malformed") {
      response.end("not-json");
    } else if (request.url === "/error") {
      response.writeHead(503).end('{"detail":"Synthetic unavailable"}');
    } else if (request.url === "/complete") {
      response.write("[");
      setTimeout(() => response.end("]"), 20);
    } else {
      response.writeHead(200);
      response.flushHeaders();
      response.write("[");
      bodyStarted = true;
      response.on("close", () => {
        connectionClosed = true;
      });
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address === "object");
  const api = new ApiClient(`http://127.0.0.1:${address.port}`);
  const deadline = consumerMode ? 30_000 : 200;
  const watchdog = new AbortController();
  const started = performance.now();
  try {
    // Consumer mode exercises the facade's real composition with its unchanged
    // 30-second default, without replacing request(), fetch(), or timers.
    const pending = consumerMode
      ? api.crm.getPractices()
      : api.request("/api/crm/practices", {}, deadline);
    const outcome = await Promise.race([
      pending.then(
        () => "unexpected success",
        (error: Error) => error.message,
      ),
      delay(deadline + 1_000, "watchdog: still pending", {
        signal: watchdog.signal,
      }),
    ]);
    const elapsedMs = Math.round(performance.now() - started);
    assert(bodyStarted, "The server must have sent headers and a partial body");
    assert.equal(outcome, "Request timeout");
    assert(elapsedMs >= deadline - 10 && elapsedMs < deadline + 1_000);
    for (let attempt = 0; attempt < 50 && !connectionClosed; attempt++) {
      await delay(10);
    }
    assert(
      connectionClosed,
      "Aborting the body must close the HTTP connection",
    );
    assert.deepEqual(await api.request("/complete", {}, 1_000), []);
    assert.deepEqual(await api.request("/empty"), {});
    await assert.rejects(api.request("/malformed"), SyntaxError);
    await assert.rejects(
      api.request("/error"),
      (error: unknown) => error instanceof ApiError && error.statusCode === 503,
    );
    assert.deepEqual(requests, [
      "GET /api/crm/practices",
      "GET /complete",
      "GET /empty",
      "GET /malformed",
      "GET /error",
    ]);
    process.stdout.write(
      `${JSON.stringify({
        consumer: consumerMode ? "api.crm.getPractices" : "api.request",
        deadline_ms: deadline,
        elapsed_ms: elapsedMs,
        body_started: bodyStarted,
        outcome,
        connection_closed: connectionClosed,
        compatibility_cases: 4,
        requests: requests.length,
      })}\n`,
    );
  } finally {
    watchdog.abort();
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
}

(process.argv.includes("--adversarial") ? adversarial() : main()).catch(
  (error: unknown) => {
    process.stderr.write(`${String(error)}\n`);
    process.exitCode = 1;
  },
);
