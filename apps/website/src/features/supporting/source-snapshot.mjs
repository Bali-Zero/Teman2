/** Development-only importer. Originals are read-only; no engine or data is shipped from here. */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const mouth = path.resolve(here, "../../../../mouth");
export const legalSourcePaths = {
  privacy: "src/app/privacy/page.tsx",
  terms: "src/app/terms/page.tsx",
  "v2-privacy": "src/app/v2/privacy/page.tsx",
  "v2-terms": "src/app/v2/terms/page.tsx",
  "v2-cookies": "src/app/v2/cookies/page.tsx",
};
export const sourceHash = (relative) =>
  createHash("sha256")
    .update(fs.readFileSync(path.join(mouth, relative)))
    .digest("hex");

function evaluate(relative, overrides = {}) {
  const source = fs.readFileSync(path.join(mouth, relative), "utf8");
  const result = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  });
  const module = { exports: {} };
  vm.runInNewContext(
    result.outputText,
    {
      module,
      exports: module.exports,
      require: (id) => {
        if (id === "react/jsx-runtime") return require(id);
        if (Object.hasOwn(overrides, id)) return overrides[id];
        throw new Error(`Unapproved source import: ${id}`);
      },
    },
    { filename: relative, timeout: 3000 },
  );
  return module.exports;
}

export function renderOriginalLegal(key) {
  const Empty = () => null;
  const module = evaluate(legalSourcePaths[key], {
    "@balizero/core/components/NavShell": { NavShell: Empty },
    "@balizero/core/components/BZLogo": { BZLogo: Empty },
    "../_components/Footer": { Footer: Empty },
  });
  return renderToStaticMarkup(module.default());
}

export function makeLegalSnapshot() {
  return Object.fromEntries(
    Object.entries(legalSourcePaths).map(([key, relative]) => {
      const dom = new JSDOM(renderOriginalLegal(key));
      const document = dom.window.document;
      const root = document.querySelector("main") ?? document.body;
      const contents = [];
      root.querySelectorAll("*").forEach((element) => {
        for (const attribute of [...element.attributes])
          if (attribute.name !== "href")
            element.removeAttribute(attribute.name);
        if (element.tagName === "H2") {
          const title = element.textContent.trim().replace(/\s+/g, " ");
          const id = `section-${contents.length + 1}`;
          element.id = id;
          contents.push({ id, title });
        }
        if (element.tagName === "TH") element.setAttribute("scope", "col");
      });
      const snapshot = {
        source: `apps/mouth/${relative}`,
        sha256: sourceHash(relative),
        title: root.querySelector("h1").textContent,
        contents,
        html: root.innerHTML,
      };
      dom.window.close();
      return [key, snapshot];
    }),
  );
}

export function loadOriginalBook() {
  const pricing = JSON.parse(
    fs.readFileSync(path.join(mouth, "data/bali-zero-prices.json"), "utf8"),
  );
  return evaluate("src/components/book/book-data.ts", {
    "@/data/team-roster": { PUBLIC_ROSTER: [] }, // R19 has an owner-reviewed public roster; no old roster is copied.
    "@/lib/pricing-snapshot": {
      getPricingSnapshotEntry: (category, key) =>
        pricing.services_by_category[category]?.[key],
    },
  });
}

export function makeBookSnapshot() {
  const book = loadOriginalBook();
  const retainedTranslationFields = [
    "chapters",
    "coverTagline",
    "coverSubtitle",
    "manifestoP1",
    "manifestoP2",
    "originP1",
    "originP2",
    "contactBody",
    "contactCta",
    "askOnWhatsApp",
    "servicesCategories",
    "teamDepts",
  ];
  return {
    source: "apps/mouth/src/components/book/book-data.ts",
    sha256: sourceHash("src/components/book/book-data.ts"),
    chapters: book.CHAPTERS.map(({ id, index }) => ({ id, index })),
    locales: book.LOCALE_LABELS,
    translations: Object.fromEntries(
      Object.entries(book.TRANSLATIONS).map(([locale, translation]) => [
        locale,
        Object.fromEntries(
          retainedTranslationFields.map((key) => [key, translation[key]]),
        ),
      ]),
    ),
    contacts: book.CONTACTS,
    // Identities and editorial fields only. Prices are never snapshotted into the website.
    services: book.SERVICES.map(
      ({
        serviceKey,
        pricingCategory,
        pricingItemKey,
        title,
        category,
        waMessage,
      }) => ({
        serviceKey,
        pricingCategory,
        pricingItemKey,
        title,
        category,
        waMessage,
      }),
    ),
  };
}

export function makeCompanySnapshot() {
  return Object.fromEntries(
    ["careers", "press"].map((key) => {
      const relative = `src/app/v2/company/${key}/page.tsx`;
      const Empty = () => null;
      const module = evaluate(relative, {
        "@balizero/core/components/NavShell": { NavShell: Empty },
        "@balizero/core/components/BZLogo": { BZLogo: Empty },
        "../../_components/Footer": { Footer: Empty },
      });
      const dom = new JSDOM(renderToStaticMarkup(module.default()));
      const main = dom.window.document.querySelector("main");
      const paragraphs = [...main.querySelectorAll("p")].map((p) =>
        p.textContent.trim().replace(/\s+/g, " "),
      );
      // The owner's real name is private under AGENTS.md. Preserve the authored invitation.
      if (key === "press")
        paragraphs[0] = paragraphs[0].replace(
          /Antonello and the team are/,
          "Our team is",
        );
      const record = {
        source: `apps/mouth/${relative}`,
        sha256: sourceHash(relative),
        title: main.querySelector("h1").textContent,
        paragraphs,
      };
      dom.window.close();
      return [key, record];
    }),
  );
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  fs.writeFileSync(
    path.join(here, "legal-content.json"),
    `${JSON.stringify(makeLegalSnapshot(), null, 2)}\n`,
  );
  fs.writeFileSync(
    path.join(here, "book-content.json"),
    `${JSON.stringify(makeBookSnapshot(), null, 2)}\n`,
  );
  fs.writeFileSync(
    path.join(here, "company-content.json"),
    `${JSON.stringify(makeCompanySnapshot(), null, 2)}\n`,
  );
}
