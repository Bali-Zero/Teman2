import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
export const dynamic = "force-dynamic";

export async function GET() {
  const decisions: Array<{
    type: string;
    title: string;
    url?: string;
    age_minutes?: number;
  }> = [];
  try {
    const { stdout } = await execFileAsync(
      "gh",
      [
        "pr",
        "list",
        "--draft",
        "--json",
        "title,url,createdAt",
        "--limit",
        "20",
      ],
      {
        timeout: 5000,
        cwd: process.env.COCKPIT_REPO_ROOT || process.cwd(),
      },
    );
    const list = JSON.parse(stdout) as Array<{
      title: string;
      url: string;
      createdAt: string;
    }>;
    for (const pr of list) {
      decisions.push({
        type: "pr_draft",
        title: pr.title,
        url: pr.url,
        age_minutes: Math.floor(
          (Date.now() - new Date(pr.createdAt).getTime()) / 60000,
        ),
      });
    }
  } catch {
    /* gh unavailable or no PRs */
  }
  return NextResponse.json({ decisions, total: decisions.length });
}
