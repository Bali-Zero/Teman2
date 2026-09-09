const sourceOrigin = "https://balizero.com";

/** Only the published cover/inline image families observed in the owned
 * article corpus. Never accept arbitrary files, encoded segments or traversal. */
export function retainedAssetPath(pathname: string): string | null {
  return /^\/static\/(?:news|blog|insights\/[a-z0-9_-]{1,60})\/[A-Za-z0-9][A-Za-z0-9_-]{0,200}\.(?:jpg|jpeg|png|webp|avif|gif)$/.test(pathname) ? pathname : null;
}

export function retainedImage(value: unknown): { src: string; sourceSrc: string } | null {
  if (typeof value !== "string" || /[\\%\s]/.test(value) || value.split("/").some((part) => part === "." || part === "..")) return null;
  try {
    const url = new URL(value, sourceOrigin);
    // Static source files have no observed query/hash contract. Reject rather
    // than carrying arbitrary request context into an image request.
    if (url.origin !== sourceOrigin || url.username || url.password || url.search || url.hash || !retainedAssetPath(url.pathname)) return null;
    return { src: `/legacy${url.pathname}`, sourceSrc: url.href };
  } catch { return null; }
}
