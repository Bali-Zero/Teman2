/**
 * Public presentation boundary. Tools and the property landing keep their
 * existing theme; property readers are included by their exact route shape.
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
  if (["/", "/news", "/team", "/contact", "/services"].includes(path))
    return true;
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "services" && parts.length === 2) return true;
  if (!editorialCategories.has(parts[0])) return false;
  if (["/property", "/property/eligibility", "/taxes/gap"].includes(path))
    return false;
  return parts.length === 1 || parts.length === 2;
}
