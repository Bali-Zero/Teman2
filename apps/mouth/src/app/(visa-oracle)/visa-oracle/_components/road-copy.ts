import type { Language } from "../_lib/flow";

/**
 * Copy the road shell adds, EN/ID, component-local because `_lib/i18n.ts`
 * is frozen for this surface (BRIEF-v2 R-6) — the SESSION_COPY pattern in
 * OracleShell.tsx. Parity (same keys, no empty value, same `{placeholders}`)
 * is pinned by road-copy.test.ts. Voice: plain, no ranking words, never a
 * visa name, never an engine identifier.
 */
export const ROAD_COPY = {
  en: {
    railOutcomeTitle: "Where this road ends",
  },
  id: {
    railOutcomeTitle: "Ujung jalan ini",
  },
} as const satisfies Record<Language, Record<string, string>>;

export type RoadCopyKey = keyof (typeof ROAD_COPY)["en"];

/** `{name}` placeholders only — no plural grammar, no markup. */
export function roadCopy(
  language: Language,
  key: RoadCopyKey,
  vars: Record<string, string | number> = {},
): string {
  return (ROAD_COPY[language][key] as string).replace(
    /\{(\w+)\}/g,
    (whole, name: string) =>
      Object.prototype.hasOwnProperty.call(vars, name)
        ? String(vars[name])
        : whole,
  );
}
