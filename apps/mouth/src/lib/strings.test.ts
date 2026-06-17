import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { STRINGS } from "./strings";

const SRC_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

/** Operator surfaces normalized by P1.3 (kita UI/UX audit 2026-06-11). */
const OPERATOR_SURFACES = [
  "app/(workspace)/intelligence/article-composer/page.tsx",
  "app/(workspace)/dashboard/page.tsx",
  "app/(workspace)/analytics/funnel/page.tsx",
  "app/(workspace)/clients/page.tsx",
  "app/(workspace)/clients/[id]/components/OracleChat.tsx",
];

/**
 * Italian microcopy that used to be hardcoded in the surfaces above.
 * Chosen to be precise enough not to false-positive on English text
 * (e.g. bare "registrati" would match English "registration").
 */
const ITALIAN_MARKERS = [
  "Incolla",
  "Es. New",
  "Caricamento",
  "Errore",
  "Nessun dato",
  '"Clienti"',
  '"Processi"',
  '"Fatture"',
  "incassato",
  "da incassare",
  '"registrati"',
  "attivi",
  "in attesa",
  "tutte pagate",
  "Chiedi all",
  "Fai una domanda",
  "Invia domanda",
  "Consultando",
  "Fonti (",
  "Riassumi",
  "scadenze",
];

describe("operator UI strings dictionary (P1.3 — one UI language)", () => {
  it("dictionary values are English (no Italian microcopy)", () => {
    const values: string[] = [
      STRINGS.dashboard.collectedSub("Rp 1M"),
      STRINGS.dashboard.casesSub(3, 1),
    ];
    const walk = (node: object) => {
      for (const value of Object.values(node)) {
        if (typeof value === "string") values.push(value);
        else if (typeof value === "object" && value !== null) walk(value);
      }
    };
    walk(STRINGS);

    for (const value of values) {
      for (const marker of ITALIAN_MARKERS) {
        expect(value, `dictionary value "${value}"`).not.toContain(
          marker.replaceAll('"', ""),
        );
      }
    }
  });

  it("normalized operator surfaces use the dictionary and carry no hardcoded Italian", () => {
    for (const surface of OPERATOR_SURFACES) {
      const source = readFileSync(path.join(SRC_ROOT, surface), "utf-8");

      expect(source, `${surface} should import the strings dictionary`).toMatch(
        /import \{ STRINGS \} from ["']@\/lib\/strings["'];/,
      );

      for (const marker of ITALIAN_MARKERS) {
        expect(
          source,
          `${surface} should not contain "${marker}"`,
        ).not.toContain(marker);
      }
    }
  });

  it("article composer renders placeholders from the dictionary", () => {
    const source = readFileSync(
      path.join(
        SRC_ROOT,
        "app/(workspace)/intelligence/article-composer/page.tsx",
      ),
      "utf-8",
    );
    expect(source).toContain(
      "placeholder={STRINGS.articleComposer.titlePlaceholder}",
    );
    expect(source).toContain(
      "placeholder={STRINGS.articleComposer.contentPlaceholder}",
    );
  });
});
