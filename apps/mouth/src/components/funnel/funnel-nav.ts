/**
 * Shared NavShell items for the 4 L1 funnels.
 *
 * Pattern: each funnel's NavShell shows Home + the other 3 siblings,
 * excluding self. So a visitor on /visa-oracle can jump to KBLI, Tax,
 * or Property directly — the previous nav omitted Property entirely.
 *
 * URLs match the real deployed routes:
 *  - visa:     https://visa.balizero.com/
 *  - kbli:     /kbli (same-origin on balizero.com)
 *  - tax:      https://tax.balizero.com/
 *  - property: /property/eligibility (same-origin, namespaced away from
 *              the pre-existing (blog)/property marketing page)
 */

type FunnelSlug = "visa" | "kbli" | "tax" | "property";

export interface NavItem {
  label: string;
  href: string;
}

const HOME: NavItem = { label: "Home", href: "https://balizero.com/" };

const SIBLINGS: Record<FunnelSlug, NavItem> = {
  visa: { label: "Visa", href: "https://visa.balizero.com/" },
  kbli: { label: "KBLI", href: "/kbli" },
  tax: { label: "Tax", href: "https://tax.balizero.com/" },
  property: { label: "Property", href: "/property/eligibility" },
};

export function getFunnelNavItems(current: FunnelSlug): NavItem[] {
  return [
    HOME,
    ...(Object.keys(SIBLINGS) as FunnelSlug[])
      .filter((slug) => slug !== current)
      .map((slug) => SIBLINGS[slug]),
  ];
}
