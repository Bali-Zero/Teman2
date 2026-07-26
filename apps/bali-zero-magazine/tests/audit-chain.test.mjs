import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

const ZERO_HASH = "0".repeat(64);

class SqliteD1Statement {
  constructor(owner, sql, values = []) {
    this.owner = owner;
    this.sql = sql;
    this.values = values;
  }

  bind(...values) {
    return new SqliteD1Statement(this.owner, this.sql, values);
  }

  _runSync() {
    const result = this.owner.sqlite.prepare(this.sql).run(...this.values);
    return {
      success: true,
      results: [],
      meta: { changes: Number(result.changes) },
    };
  }

  async run() {
    return this._runSync();
  }

  async first() {
    return this.owner.sqlite.prepare(this.sql).get(...this.values) ?? null;
  }

  async all() {
    return {
      success: true,
      results: this.owner.sqlite.prepare(this.sql).all(...this.values),
      meta: { changes: 0 },
    };
  }
}

class SqliteD1Database {
  constructor() {
    this.sqlite = new DatabaseSync(":memory:");
    this.sqlite.exec("PRAGMA foreign_keys = ON");
    this.sqlite.exec(
      readFileSync(
        new URL("../drizzle/0000_magazine_core.sql", import.meta.url),
        "utf8",
      ).replaceAll("--> statement-breakpoint", ""),
    );
    this.beforeNextBatch = null;
  }

  prepare(sql) {
    return new SqliteD1Statement(this, sql);
  }

  async batch(statements) {
    const beforeBatch = this.beforeNextBatch;
    this.beforeNextBatch = null;
    if (beforeBatch) await beforeBatch();

    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => statement._runSync());
      this.sqlite.exec("COMMIT");
      return results;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }

  all(sql, ...values) {
    return this.sqlite.prepare(sql).all(...values);
  }

  get(sql, ...values) {
    return this.sqlite.prepare(sql).get(...values) ?? null;
  }
}

function u32(value) {
  const bytes = Buffer.alloc(4);
  bytes.writeUInt32BE(value);
  return bytes;
}

function u64(value) {
  const bytes = Buffer.alloc(8);
  bytes.writeBigUInt64BE(BigInt(value));
  return bytes;
}

test("audit preimage is byte-exact RFC 8785 JCS with raw hash bytes", async () => {
  const audit = await import("../lib/server/audit-chain.ts");
  const payload = { z: [3, -0, "é"], a: { beta: true, alpha: null } };
  const canonical = '{"a":{"alpha":null,"beta":true},"z":[3,0,"é"]}';

  assert.equal(audit.canonicalizeAuditPayload(payload), canonical);

  const stream = Buffer.from("révisions", "utf8");
  const expected = Buffer.concat([
    Buffer.from("BZM-AUDIT-EVENT-V1", "ascii"),
    Buffer.from([0]),
    u32(stream.length),
    stream,
    u64(7),
    Buffer.from("ab".repeat(32), "hex"),
    u64(Buffer.byteLength(canonical, "utf8")),
    Buffer.from(canonical, "utf8"),
  ]);
  const actual = audit.buildAuditEventPreimage({
    streamId: "re\u0301visions",
    streamSeq: 7,
    previousEventHash: "ab".repeat(32),
    payload,
  });

  assert.deepEqual(Buffer.from(actual), expected);
});

test("audit appends genesis and successor events with a byte-exact hash chain", async () => {
  const { createAuditChain, hashAuditEvent } =
    await import("../lib/server/audit-chain.ts");
  const db = new SqliteD1Database();
  const audit = createAuditChain(db);

  const firstPayload = { action: "publish", revision: 1 };
  const first = await audit.appendAuditEvent({
    event_id: "event-1",
    stream_id: "publication",
    payload: firstPayload,
  });
  const secondPayload = { revision: 2, action: "supersede" };
  const second = await audit.appendAuditEvent({
    event_id: "event-2",
    stream_id: "publication",
    payload: secondPayload,
  });

  assert.equal(first.stream_seq, 1);
  assert.equal(first.previous_event_hash, ZERO_HASH);
  assert.equal(
    first.event_hash,
    await hashAuditEvent({
      streamId: "publication",
      streamSeq: 1,
      previousEventHash: ZERO_HASH,
      payload: firstPayload,
    }),
  );
  assert.equal(second.stream_seq, 2);
  assert.equal(second.previous_event_hash, first.event_hash);
  assert.deepEqual(
    {
      ...db.get(
        "SELECT * FROM audit_stream_heads WHERE stream_id = ?",
        "publication",
      ),
    },
    {
      stream_id: "publication",
      stream_seq: 2,
      event_hash: second.event_hash,
    },
  );
});

test("audit stream CAS conflict rolls back the event and preserves the winner", async () => {
  const { createAuditChain } = await import("../lib/server/audit-chain.ts");
  const db = new SqliteD1Database();
  const contender = createAuditChain(db);
  const winner = createAuditChain(db);

  db.beforeNextBatch = async () => {
    await winner.appendAuditEvent({
      event_id: "event-winner",
      stream_id: "publication",
      payload: { winner: true },
    });
  };

  await assert.rejects(
    contender.appendAuditEvent({
      event_id: "event-loser",
      stream_id: "publication",
      payload: { winner: false },
    }),
    /CAS conflict.*rolled back/i,
  );

  assert.deepEqual(
    db
      .all("SELECT event_id, stream_seq FROM audit_events ORDER BY stream_seq")
      .map((row) => ({ ...row })),
    [{ event_id: "event-winner", stream_seq: 1 }],
  );
  assert.equal(
    db.get(
      "SELECT stream_seq FROM audit_stream_heads WHERE stream_id = ?",
      "publication",
    ).stream_seq,
    1,
  );
});
