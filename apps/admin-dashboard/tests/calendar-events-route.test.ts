import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

/**
 * Two distinct vulnerability classes on this route, both from CodeQL
 * (js/command-line-injection #2311/#2312/#2313, 2026-08-21) and a follow-up
 * security review on the first fix:
 *
 * 1. SHELL injection (CWE-78) — the original bug. GET/POST/DELETE built a
 *    `gog` shell command with a template string and ran it via
 *    `child_process.exec`, which spawns `/bin/sh -c <string>`. Fixed by
 *    switching to `execFile` + an argv array: no shell is ever spawned, so
 *    shell metacharacters in a value are inert wherever they reach `gog` at
 *    all.
 * 2. ARGUMENT injection / flag smuggling (CWE-88) — execFile's own residual
 *    risk. gog is built on alecthomas/kong, which (like effectively every
 *    CLI-parsing library) reads any `-`-prefixed argv token as a candidate
 *    FLAG regardless of which array slot it lands in. A calendarId of
 *    `--upload-file=/etc/passwd` carries no shell risk but could still be
 *    reinterpreted by gog itself. Fixed by allow-listing every field to the
 *    shape it must have (never a blocklist), explicitly rejecting anything
 *    that starts with `-`.
 *
 * `child_process` is mocked at the module the route imports, so `exec` and
 * `execFile` resolve to the same spies the route calls.
 */
const execFileMock = vi.fn(
  (
    _file: string,
    _args: string[],
    cb: (err: Error | null, res: { stdout: string; stderr: string }) => void,
  ) => {
    cb(null, { stdout: '{"events":[]}', stderr: "" });
  },
);
const execMock = vi.fn();

vi.mock("child_process", () => ({
  execFile: (...args: unknown[]) =>
    (execFileMock as (...a: unknown[]) => unknown)(...args),
  exec: (...args: unknown[]) =>
    (execMock as (...a: unknown[]) => unknown)(...args),
}));

const { GET, POST, DELETE } = await import("@/app/api/calendar/events/route");

const SHELL_PAYLOAD = '"; touch /tmp/pwned; echo "';
const VALID_CAL_ID = "team@balizero.com";

function getReq(search: string): NextRequest {
  return new NextRequest(
    new URL(`https://admin.balizero.com/api/calendar/events${search}`),
  );
}

function postReq(body: Record<string, unknown>): NextRequest {
  return new NextRequest(
    new URL("https://admin.balizero.com/api/calendar/events"),
    { method: "POST", body: JSON.stringify(body) },
  );
}

beforeEach(() => {
  execFileMock.mockClear();
  execMock.mockClear();
  execFileMock.mockImplementation((_file, _args, cb) =>
    cb(null, { stdout: '{"events":[]}', stderr: "" }),
  );
});

describe("/api/calendar/events GET", () => {
  it("GUILT (shell): a calendarId with shell metacharacters is rejected by shape validation, never reaches a process", async () => {
    const res = await GET(
      getReq(`?calendarId=${encodeURIComponent(SHELL_PAYLOAD)}`),
    );
    expect(res.status).toBe(400);
    expect(execMock).not.toHaveBeenCalled();
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a calendarId starting with '-' is rejected, not passed to gog", async () => {
    const res = await GET(
      getReq(`?calendarId=${encodeURIComponent("--upload-file=/etc/passwd")}`),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a days value starting with '-' is rejected", async () => {
    const res = await GET(
      getReq(
        `?calendarId=${VALID_CAL_ID}&days=${encodeURIComponent("--evil")}`,
      ),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a max value starting with '-' is rejected", async () => {
    const res = await GET(
      getReq(`?calendarId=${VALID_CAL_ID}&max=${encodeURIComponent("--evil")}`),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("INNOCENCE: a normal request resolves the parsed events with the exact argv", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, {
        stdout: JSON.stringify({
          events: [{ id: "e1", summary: "Kickoff" }],
        }),
        stderr: "",
      }),
    );
    const res = await GET(getReq(`?calendarId=${VALID_CAL_ID}&days=7&max=10`));
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.success).toBe(true);
    expect(json.events).toEqual([{ id: "e1", summary: "Kickoff" }]);
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    expect(args).toEqual([
      "calendar",
      "events",
      VALID_CAL_ID,
      "--days",
      "7",
      "--max",
      "10",
      "--json",
    ]);
  });

  it("INNOCENCE: 'primary' is an accepted calendarId shape", async () => {
    const res = await GET(getReq("?calendarId=primary"));
    expect(res.status).toBe(200);
    expect(execFileMock).toHaveBeenCalledTimes(1);
  });
});

describe("/api/calendar/events POST", () => {
  const validBody = {
    summary: "Team sync",
    from: "2026-08-21T10:00:00Z",
    to: "2026-08-21T11:00:00Z",
  };

  it("GUILT (shell): a summary with shell metacharacters survives as one inert argv element (execFile, not exec)", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: "{}", stderr: "" }),
    );
    const res = await POST(
      postReq({
        ...validBody,
        summary: SHELL_PAYLOAD,
        description: "`whoami`",
      }),
    );
    expect(res.status).toBe(200);
    expect(execMock).not.toHaveBeenCalled();
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    // Injected content must not have grown the argv beyond the fields
    // actually supplied (summary/from/to/description + fixed flags + --json).
    expect(args).toEqual([
      "calendar",
      "create",
      "ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com",
      "--summary",
      SHELL_PAYLOAD,
      "--from",
      "2026-08-21T10:00:00Z",
      "--to",
      "2026-08-21T11:00:00Z",
      "--description",
      "`whoami`",
      "--json",
    ]);
  });

  it("GUILT (argv flag smuggling): a summary starting with '-' is rejected, not passed to gog", async () => {
    const res = await POST(
      postReq({ ...validBody, summary: "--upload-file=/etc/passwd" }),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a description starting with '-' is rejected", async () => {
    const res = await POST(
      postReq({ ...validBody, description: "--evil-flag" }),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a location starting with '-' is rejected", async () => {
    const res = await POST(postReq({ ...validBody, location: "--evil-flag" }));
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): an attendees value starting with '-' is rejected", async () => {
    const res = await POST(postReq({ ...validBody, attendees: "--evil-flag" }));
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a calendarId starting with '-' is rejected", async () => {
    const res = await POST(
      postReq({ ...validBody, calendarId: "--upload-file=/etc/passwd" }),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT: a non-ISO 'from'/'to' (including a flag-shaped one) is rejected", async () => {
    const res = await POST(postReq({ ...validBody, from: "--evil" }));
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("INNOCENCE: a legitimate create still works and rejects incomplete payloads", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: JSON.stringify({ id: "evt1" }), stderr: "" }),
    );
    const res = await POST(postReq(validBody));
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ success: true, event: { id: "evt1" } });

    execFileMock.mockClear();
    const bad = await POST(postReq({ summary: "No dates" }));
    expect(bad.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("INNOCENCE: description/location/attendees with ordinary hyphens still work", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: "{}", stderr: "" }),
    );
    const res = await POST(
      postReq({
        ...validBody,
        description: "Q3 planning - budget review",
        location: "Meeting Room - 2nd floor",
        attendees: "a@balizero.com,b@balizero.com",
      }),
    );
    expect(res.status).toBe(200);
    const [, args] = execFileMock.mock.calls[0];
    expect(args).toContain("--description");
    expect(args).toContain("Q3 planning - budget review");
    expect(args).toContain("--attendees");
    expect(args).toContain("a@balizero.com,b@balizero.com");
  });
});

describe("/api/calendar/events DELETE", () => {
  it("GUILT (shell): an eventId with shell metacharacters is rejected by shape validation, never reaches a process", async () => {
    const res = await DELETE(
      getReq(
        `?eventId=${encodeURIComponent(SHELL_PAYLOAD)}&calendarId=${VALID_CAL_ID}`,
      ),
    );
    expect(res.status).toBe(400);
    expect(execMock).not.toHaveBeenCalled();
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): an eventId starting with '-' is rejected, not passed to gog", async () => {
    const res = await DELETE(
      getReq(
        `?eventId=${encodeURIComponent("--force")}&calendarId=${VALID_CAL_ID}`,
      ),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("GUILT (argv flag smuggling): a calendarId starting with '-' is rejected", async () => {
    const res = await DELETE(
      getReq(
        `?eventId=abc123&calendarId=${encodeURIComponent("--upload-file=/etc/passwd")}`,
      ),
    );
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("INNOCENCE: missing eventId is rejected before any process spawns", async () => {
    const res = await DELETE(getReq(`?calendarId=${VALID_CAL_ID}`));
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });

  it("INNOCENCE: a valid eventId+calendarId deletes with the exact argv", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: "", stderr: "" }),
    );
    const res = await DELETE(
      getReq(`?eventId=abc123XYZ&calendarId=${VALID_CAL_ID}`),
    );
    expect(res.status).toBe(200);
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    expect(args).toEqual([
      "calendar",
      "delete",
      VALID_CAL_ID,
      "abc123XYZ",
      "--force",
    ]);
  });
});
