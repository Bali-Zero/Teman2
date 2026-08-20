import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

/**
 * CodeQL js/command-line-injection #2311/#2312/#2313 (2026-08-21):
 * GET/POST/DELETE built a `gog` shell command with a template string and ran
 * it via `child_process.exec`, which spawns `/bin/sh -c <string>`. A
 * `calendarId`/`summary`/`eventId` containing shell metacharacters (`;`,
 * `$(...)`, backticks, a stray `"`) could break out of its quoted slot and
 * run arbitrary shell. The fix swaps `exec` + string concatenation for
 * `execFile` + an argv array — no shell is ever spawned, so each array
 * element reaches the `gog` binary as exactly one argument no matter what
 * characters it contains.
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

describe("/api/calendar/events GET — command injection", () => {
  it("GUILT: a calendarId with shell metacharacters never reaches a shell", async () => {
    const res = await GET(
      getReq(`?calendarId=${encodeURIComponent(SHELL_PAYLOAD)}`),
    );
    expect(res.status).toBe(200);
    expect(execMock).not.toHaveBeenCalled();
    expect(execFileMock).toHaveBeenCalledTimes(1);
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    // The whole payload must survive as ONE argv element — never split,
    // never interpreted, never used to grow the args array.
    expect(args).toContain(SHELL_PAYLOAD);
    expect(args.filter((a: string) => a === SHELL_PAYLOAD)).toHaveLength(1);
  });

  it("INNOCENCE: a normal request resolves the parsed events", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, {
        stdout: JSON.stringify({
          events: [{ id: "e1", summary: "Kickoff" }],
        }),
        stderr: "",
      }),
    );
    const res = await GET(getReq("?calendarId=team-cal&days=7&max=10"));
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.success).toBe(true);
    expect(json.events).toEqual([{ id: "e1", summary: "Kickoff" }]);
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    expect(args).toEqual([
      "calendar",
      "events",
      "team-cal",
      "--days",
      "7",
      "--max",
      "10",
      "--json",
    ]);
  });
});

describe("/api/calendar/events POST — command injection", () => {
  it("GUILT: a summary with shell metacharacters never reaches a shell", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: "{}", stderr: "" }),
    );
    const res = await POST(
      postReq({
        summary: SHELL_PAYLOAD,
        from: "2026-08-21T10:00:00Z",
        to: "2026-08-21T11:00:00Z",
        description: "`whoami`",
      }),
    );
    expect(res.status).toBe(200);
    expect(execMock).not.toHaveBeenCalled();
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    expect(args).toContain(SHELL_PAYLOAD);
    expect(args).toContain("`whoami`");
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

  it("INNOCENCE: a legitimate create still works and rejects incomplete payloads", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: JSON.stringify({ id: "evt1" }), stderr: "" }),
    );
    const res = await POST(
      postReq({
        summary: "Team sync",
        from: "2026-08-21T10:00:00Z",
        to: "2026-08-21T11:00:00Z",
      }),
    );
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ success: true, event: { id: "evt1" } });

    execFileMock.mockClear();
    const bad = await POST(postReq({ summary: "No dates" }));
    expect(bad.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });
});

describe("/api/calendar/events DELETE — command injection", () => {
  it("GUILT: an eventId with shell metacharacters never reaches a shell", async () => {
    execFileMock.mockImplementation((_file, _args, cb) =>
      cb(null, { stdout: "", stderr: "" }),
    );
    const res = await DELETE(
      getReq(`?eventId=${encodeURIComponent(SHELL_PAYLOAD)}&calendarId=cal1`),
    );
    expect(res.status).toBe(200);
    expect(execMock).not.toHaveBeenCalled();
    const [file, args] = execFileMock.mock.calls[0];
    expect(file).toBe("/opt/homebrew/bin/gog");
    expect(args).toEqual([
      "calendar",
      "delete",
      "cal1",
      SHELL_PAYLOAD,
      "--force",
    ]);
  });

  it("INNOCENCE: missing eventId is rejected before any process spawns", async () => {
    const res = await DELETE(getReq("?calendarId=cal1"));
    expect(res.status).toBe(400);
    expect(execFileMock).not.toHaveBeenCalled();
  });
});
