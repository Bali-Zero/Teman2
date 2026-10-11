import { NextResponse } from "next/server";

// Which commit is this build made from? Two sources, in this order:
//   1. VERCEL_GIT_COMMIT_SHA - injected by Vercel for a git-sourced deployment
//      (autoExposeSystemEnvs is on for this project).
//   2. BUILD_COMMIT_SHA - passed by `scripts/vercel_prod_deploy.py --upload`, because a CLI
//      upload of a source tree has no git metadata and the first source is then absent.
// `||` and not `??` on purpose: an empty string (an unset-but-declared env) must fall through
// to the next source rather than be reported as the commit. Neither exists locally: null.
//
// This exists so production can answer "which commit am I serving?" without anyone having to
// trust a deployment record. On 2026-07-27 balizero.com served 13-hour-old code while every
// registry looked healthy, and the only way to catch it was to compare a rendered route against
// the repo by hand. A registry says what was ANNOUNCED; this says what is RUNNING.
// The repository is public, so the SHA is not a secret.
//
// Read at module scope on purpose: it is baked into the build, never read per request.
const COMMIT =
  process.env.VERCEL_GIT_COMMIT_SHA || process.env.BUILD_COMMIT_SHA || null;

export async function GET() {
  return NextResponse.json({
    status: "ok",
    timestamp: Date.now(),
    commit: COMMIT,
  });
}
