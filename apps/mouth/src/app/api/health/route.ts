import { NextResponse } from "next/server";

// Which commit is this build made from? Vercel injects VERCEL_GIT_COMMIT_SHA at build time
// (autoExposeSystemEnvs is on for this project); there is no such env locally, hence null.
//
// This exists so production can answer "which commit am I serving?" without anyone having to
// trust a deployment record. On 2026-07-27 balizero.com served 13-hour-old code while every
// registry looked healthy, and the only way to catch it was to compare a rendered route against
// the repo by hand. A registry says what was ANNOUNCED; this says what is RUNNING.
// The repository is public, so the SHA is not a secret.
//
// Read at module scope on purpose: it is baked into the build, never read per request.
const COMMIT = process.env.VERCEL_GIT_COMMIT_SHA ?? null;

export async function GET() {
  return NextResponse.json({
    status: "ok",
    timestamp: Date.now(),
    commit: COMMIT,
  });
}
