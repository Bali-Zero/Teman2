import { retainedApiUnavailable } from "../../../lib/server/retained-handoff";

// No broad proxy: only the registry's declared dependencies return the
// explicit owner-required response. Unknown endpoints remain true 404s.
export const GET = retainedApiUnavailable;
export const HEAD = retainedApiUnavailable;
export const POST = retainedApiUnavailable;
export const PUT = retainedApiUnavailable;
export const PATCH = retainedApiUnavailable;
export const DELETE = retainedApiUnavailable;
export const OPTIONS = retainedApiUnavailable;
