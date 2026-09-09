/** Presentation-only extract: never completes or rewrites the publisher's prose. */
export function editorialExcerpt(source: string | undefined, limit = 240): string {
  const text = (source ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  const sentences = [...new Intl.Segmenter("en", { granularity: "sentence" }).segment(text)];
  let complete = "";
  for (const { segment } of sentences) {
    const next = `${complete}${segment}`;
    if (next.trim().length > limit) break;
    complete = next;
  }
  if (complete.trim().length >= 60 && /[.!?][”’"')\]]?$/.test(complete.trim())) return complete.trim();
  // One long sentence: mark the omission, cutting only at a word boundary.
  const prefix = text.slice(0, limit - 1);
  const boundary = prefix.lastIndexOf(" ");
  return boundary > 0 ? `${prefix.slice(0, boundary).replace(/[,;:]$/, "")}…` : "";
}
