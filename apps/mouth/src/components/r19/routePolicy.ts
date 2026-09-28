/**
 * Public presentation boundary. Tools keep their existing theme; property
 * readers and the property landing are included by their exact route shape.
 *
 * `/property/eligibility` (the tool) moved to R19 2026-09-28 (owner decision,
 * spec-property-check.md) — its own layout now mounts `R19Presentation`.
 * `/property` (the static (blog) landing page) now uses the R19 skin.
 */
const editorialCategories = new Set([
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
  "immigration",
  "lifestyle",
  "tech",
  "tax",
  "tax-legal",
  "digital-nomad",
  "bali-news",
]);

export function isR19Route(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (
    [
      "/",
      "/news",
      "/team",
      "/contact",
      "/services",
      "/privacy",
      "/terms",
      "/cookies",
      "/about",
      "/careers",
      "/press",
    ].includes(path)
  )
    return true;
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "services" && parts.length === 2) return true;
  if (!editorialCategories.has(parts[0])) return false;
  if (["/taxes/gap"].includes(path)) return false;
  return parts.length === 1 || parts.length === 2;
}
