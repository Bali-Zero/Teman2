import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AssignmentTargetsError,
  fetchAssignmentTargets,
} from "./assignment-targets";

const URL_UNDER_TEST = "/api/crm/garuda/assignment-targets";

function stubFetch(
  implementation: (input: unknown, init?: unknown) => unknown,
) {
  const fn = vi.fn(implementation);
  vi.stubGlobal("fetch", fn);
  return fn;
}

function response(status: number, body: unknown, ok = status < 400) {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchAssignmentTargets", () => {
  it("asks the CRM-side endpoint same-origin, never the Fly host directly", async () => {
    // The transport convention `api-client.ts`'s header comment says was paid
    // for with a live 401: `NEXT_PUBLIC_API_URL` drops the httpOnly session
    // cookie and the proxy's CSRF promotion.
    const fetchMock = stubFetch(() => response(200, { items: [] }));

    await fetchAssignmentTargets();

    expect(fetchMock).toHaveBeenCalledWith(URL_UNDER_TEST, {
      method: "GET",
      credentials: "same-origin",
      signal: undefined,
    });
  });

  it("returns the items the gate accepts", async () => {
    stubFetch(() =>
      response(200, {
        items: [
          { email: "a@example.test", label: "A" },
          { email: "b@example.test", label: "B (b@example.test)" },
        ],
      }),
    );

    await expect(fetchAssignmentTargets()).resolves.toEqual([
      { email: "a@example.test", label: "A" },
      { email: "b@example.test", label: "B (b@example.test)" },
    ]);
  });

  it("drops a row that is not an {email,label} pair instead of rendering it", async () => {
    stubFetch(() =>
      response(200, {
        items: [
          { email: "a@example.test", label: "A" },
          { email: "no-label@example.test" },
          { label: "no-email" },
          null,
          "a@example.test",
        ],
      }),
    );

    await expect(fetchAssignmentTargets()).resolves.toEqual([
      { email: "a@example.test", label: "A" },
    ]);
  });

  it("reports a refusal with its status (a non-admin gets 403)", async () => {
    stubFetch(() => response(403, { detail: "Admin role required" }));

    const error = await fetchAssignmentTargets().catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(AssignmentTargetsError);
    expect((error as AssignmentTargetsError).httpStatus).toBe(403);
  });

  it("reports a network failure with a null status", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });

    const error = await fetchAssignmentTargets().catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(AssignmentTargetsError);
    expect((error as AssignmentTargetsError).httpStatus).toBeNull();
    expect((error as AssignmentTargetsError).sourceCause).toBeInstanceOf(
      TypeError,
    );
  });

  it("refuses a 200 whose body is not the {items:[...]} shape", async () => {
    stubFetch(() => response(200, [{ email: "a@example.test", label: "A" }]));

    const error = await fetchAssignmentTargets().catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(AssignmentTargetsError);
    expect((error as AssignmentTargetsError).httpStatus).toBe(200);
  });
});
