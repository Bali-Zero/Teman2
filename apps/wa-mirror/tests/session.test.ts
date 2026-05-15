// session.test.ts — unit tests for the wa-mirror close-code classification.
//
// The reconnect loop in session.ts hinges on one decision: is a Baileys
// `connection: "close"` event TERMINAL (needs a fresh QR) or TRANSIENT
// (recreate the socket)? Getting that wrong is the bug this whole branch
// fixes — the pre-2026-05-14 code treated restartRequired (515) as a dead
// end, so every session died the moment WhatsApp asked for the standard
// post-pairing restart.
//
// `isTerminalCloseCode` and `mapCloseReason` are pure functions, so we test
// them directly without standing up a real Baileys socket or a Postgres pool.

import { DisconnectReason } from "@whiskeysockets/baileys";
import { describe, expect, it } from "vitest";

import { isTerminalCloseCode, mapCloseReason } from "../bridge/session.js";

describe("isTerminalCloseCode", () => {
  it("treats loggedOut (401) as terminal — needs a fresh QR scan", () => {
    expect(isTerminalCloseCode(DisconnectReason.loggedOut)).toBe(true);
    expect(isTerminalCloseCode(401)).toBe(true);
  });

  it("treats restartRequired (515) as NON-terminal — the post-pairing bounce", () => {
    // This is the exact code that killed every session before this branch:
    // WhatsApp ALWAYS sends 515 right after a QR pairing, expecting the
    // client to recreate the socket.
    expect(isTerminalCloseCode(DisconnectReason.restartRequired)).toBe(false);
    expect(isTerminalCloseCode(515)).toBe(false);
  });

  it("treats connectionLost / timedOut (408) as NON-terminal", () => {
    expect(isTerminalCloseCode(DisconnectReason.connectionLost)).toBe(false);
    expect(isTerminalCloseCode(DisconnectReason.timedOut)).toBe(false);
    expect(isTerminalCloseCode(408)).toBe(false);
  });

  it("treats connectionClosed (428) as NON-terminal", () => {
    expect(isTerminalCloseCode(DisconnectReason.connectionClosed)).toBe(false);
    expect(isTerminalCloseCode(428)).toBe(false);
  });

  it("treats connectionReplaced (440) as NON-terminal", () => {
    expect(isTerminalCloseCode(DisconnectReason.connectionReplaced)).toBe(false);
    expect(isTerminalCloseCode(440)).toBe(false);
  });

  it("treats badSession (500) as NON-terminal — recoverable by reconnect", () => {
    expect(isTerminalCloseCode(DisconnectReason.badSession)).toBe(false);
    expect(isTerminalCloseCode(500)).toBe(false);
  });

  it("treats the no-status-code close (0) as NON-terminal", () => {
    // Baileys reports code 0 when the socket closes before any handshake —
    // e.g. an unscanned QR window expiring. Must keep retrying.
    expect(isTerminalCloseCode(0)).toBe(false);
  });

  it("treats an unknown code as NON-terminal (fail-open to reconnect)", () => {
    expect(isTerminalCloseCode(9999)).toBe(false);
  });
});

describe("mapCloseReason", () => {
  it("maps the known Baileys codes to stable snake_case strings", () => {
    expect(mapCloseReason(DisconnectReason.loggedOut)).toBe("logged_out");
    expect(mapCloseReason(DisconnectReason.restartRequired)).toBe(
      "restart_required"
    );
    expect(mapCloseReason(DisconnectReason.connectionLost)).toBe(
      "connection_lost"
    );
    expect(mapCloseReason(DisconnectReason.connectionClosed)).toBe(
      "connection_closed"
    );
    expect(mapCloseReason(DisconnectReason.connectionReplaced)).toBe(
      "connection_replaced"
    );
    expect(mapCloseReason(DisconnectReason.badSession)).toBe("bad_session");
  });

  it("connectionLost and timedOut share code 408 — both map to connection_lost", () => {
    // Baileys defines DisconnectReason.connectionLost === DisconnectReason.timedOut
    // === 408. The switch in mapCloseReason matches `connectionLost` first, so
    // 408 always reads as "connection_lost". The `timedOut` case is dead code;
    // this test documents the collision rather than pretending it returns
    // "timed_out".
    expect(DisconnectReason.timedOut).toBe(DisconnectReason.connectionLost);
    expect(mapCloseReason(DisconnectReason.timedOut)).toBe("connection_lost");
    expect(mapCloseReason(408)).toBe("connection_lost");
  });

  it("falls back to code_<n> for unmapped codes", () => {
    expect(mapCloseReason(9999)).toBe("code_9999");
    expect(mapCloseReason(0)).toBe("code_0");
  });

  it("never returns a string longer than the 64-char disconnect_reason column", () => {
    // markDisconnected slices to 64; mapCloseReason should already be short.
    for (const code of [0, 401, 408, 428, 440, 500, 515, 1234567890]) {
      expect(mapCloseReason(code).length).toBeLessThanOrEqual(64);
    }
  });
});
