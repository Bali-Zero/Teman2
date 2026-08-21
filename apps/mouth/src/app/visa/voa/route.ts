export const dynamic = "force-dynamic";
export const revalidate = 0;

const TOMBSTONE_HEADERS = {
  "cache-control": "no-store, max-age=0",
  "content-type": "text/plain; charset=utf-8",
  "x-robots-tag": "noindex, nofollow",
};

/** Retired public URL. GARUDA remains an owner-only internal tool. */
export function GET(): Response {
  return new Response("Not Found\n", {
    status: 404,
    headers: TOMBSTONE_HEADERS,
  });
}

export function HEAD(): Response {
  return new Response(null, { status: 404, headers: TOMBSTONE_HEADERS });
}
