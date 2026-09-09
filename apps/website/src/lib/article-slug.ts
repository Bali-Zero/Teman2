/** Published legacy identifiers can contain underscores and repeated/trailing hyphens.
 * Keep that identity intact while excluding path separators and URL syntax. */
export function isArticleSlug(value: unknown): value is string {
  return typeof value === "string" && value.length <= 200 && /^[a-z0-9][a-z0-9_-]*$/.test(value);
}
