import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * `/api/clients` replaced `/api/postgres/query?table=clients`, which had no
 * column list and no row scoping. These tests pin the two properties that make
 * the replacement worth having — the narrow projection and the per-user row
 * scope — plus the header it reads to decide the scope.
 *
 * `pg` is mocked by its bare specifier, the same one the route imports, so the
 * mock and the route resolve to one module identity.
 */
const query = vi.fn();
const release = vi.fn();
const connect = vi.fn(async () => ({ query, release }));

vi.mock("pg", () => ({
  Pool: class {
    connect = connect;
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

const { GET } = await import("@/app/api/clients/route");

function request(
  headers: Record<string, string> = {},
  url = "https://admin.balizero.com/api/clients",
): Request {
  return new Request(url, { headers: new Headers(headers) });
}

beforeEach(() => {
  query.mockReset();
  query.mockResolvedValue({ rows: [], rowCount: 0 });
  release.mockClear();
  connect.mockClear();
});

describe("/api/clients — projection", () => {
  it("never selects *, and asks only for the seven agreed columns", async () => {
    await GET(request({ "x-admin-email": "zero@balizero.com" }));
    const [sql] = query.mock.calls[0];
    expect(sql).not.toContain("*");
    for (const col of [
      "id",
      "full_name",
      "email",
      "phone",
      "status",
      "assigned_to",
      "created_at",
    ]) {
      expect(sql).toContain(col);
    }
  });

  it("excludes soft-deleted rows on both branches", async () => {
    await GET(request({ "x-admin-email": "zero@balizero.com" }));
    await GET(request({ "x-admin-email": "ari@balizero.com" }));
    for (const [sql] of query.mock.calls) {
      expect(sql).toContain("deleted_at IS NULL");
    }
  });
});

describe("/api/clients — row scope", () => {
  it("GUILT: a non-full-access admin is scoped to their own assignments", async () => {
    await GET(request({ "x-admin-email": "ari@balizero.com" }));
    const [sql, params] = query.mock.calls[0];
    expect(sql).toContain("assigned_to = $1");
    expect(params[0]).toBe("ari@balizero.com");
  });

  it("GUILT: no header at all is scoped, not escalated", async () => {
    await GET(request({}));
    const [sql, params] = query.mock.calls[0];
    expect(sql).toContain("assigned_to = $1");
    expect(params[0]).toBe("");
  });

  it("GUILT: x-user-email is not an authentication header", async () => {
    // The header the route originally read. Nothing stamps it, so honouring it
    // would mean trusting a value the caller types.
    await GET(request({ "x-user-email": "zero@balizero.com" }));
    const [sql] = query.mock.calls[0];
    expect(sql).toContain("assigned_to = $1");
  });

  it("INNOCENCE: each of the three full-access users reads the whole book", async () => {
    for (const who of [
      "zero@balizero.com",
      "antonellosiano@balizero.com",
      "asya@balizero.com",
    ]) {
      query.mockClear();
      await GET(request({ "x-admin-email": who }));
      const [sql] = query.mock.calls[0];
      expect(sql).not.toContain("assigned_to = $1");
    }
  });
});

describe("/api/clients — pagination", () => {
  it("binds finite numbers for a normal page", async () => {
    await GET(
      request(
        { "x-admin-email": "zero@balizero.com" },
        "https://admin.balizero.com/api/clients?page=3",
      ),
    );
    const [, params] = query.mock.calls[0];
    expect(params).toEqual([100, 200]);
  });

  it.each(["abc", "", "-4", "1e999", "NaN"])(
    "never binds a non-finite OFFSET for page=%s",
    async (page) => {
      query.mockClear();
      await GET(
        request(
          { "x-admin-email": "zero@balizero.com" },
          `https://admin.balizero.com/api/clients?page=${encodeURIComponent(page)}`,
        ),
      );
      const [, params] = query.mock.calls[0];
      const offset = params[params.length - 1];
      expect(Number.isFinite(offset)).toBe(true);
      expect(offset).toBeGreaterThanOrEqual(0);
    },
  );
});

describe("/api/clients — failure", () => {
  it("returns a generic 500 without echoing the pg error", async () => {
    query.mockRejectedValueOnce(
      new Error('connection to server at "10.0.0.1", port 5432 failed'),
    );
    const res = await GET(request({ "x-admin-email": "zero@balizero.com" }));
    expect(res.status).toBe(500);
    const body = await res.json();
    expect(JSON.stringify(body)).not.toContain("10.0.0.1");
  });

  it("releases the connection even when the query throws", async () => {
    query.mockRejectedValueOnce(new Error("boom"));
    await GET(request({ "x-admin-email": "zero@balizero.com" }));
    expect(release).toHaveBeenCalled();
  });
});
