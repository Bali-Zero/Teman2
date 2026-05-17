/**
 * GET /api/cockpit/decisions — list draft PRs as "pending decisions" count.
 *
 * Read-only: shells out to `gh pr list --draft` against the monorepo
 * checkout pointed to by COCKPIT_REPO_ROOT. Returns the parsed JSON
 * array as-is. MVP does NOT expose merge / approve actions.
 */
import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

export const dynamic = "force-dynamic";

const execFileAsync = promisify(execFile);

export async function GET() {
  const cwd =
    process.env.COCKPIT_REPO_ROOT ?? "/Users/nuzantara/Desktop/nuzantara";

  try {
    const { stdout } = await execFileAsync(
      "gh",
      [
        "pr",
        "list",
        "--draft",
        "--json",
        "title,url,createdAt,number,author",
        "--limit",
        "20",
      ],
      { cwd, timeout: 8000 },
    );
    const parsed = JSON.parse(stdout || "[]");
    return NextResponse.json({
      count: Array.isArray(parsed) ? parsed.length : 0,
      items: parsed,
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    // gh CLI absence / auth failure must not crash the page — return
    // count 0 and surface the message so the Home tile shows a sensible
    // fallback ("unavailable").
    return NextResponse.json({ count: 0, items: [], error: msg });
  }
}
