import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import legal from "./legal-content.json";
import book from "./book-content.json";
import company from "./company-content.json";
import {
  legalSourcePaths,
  renderOriginalLegal,
  loadOriginalBook,
  makeBookSnapshot,
  makeCompanySnapshot,
} from "./source-snapshot.mjs";
import { bookHref, bookLocale, bookServices } from "./book-model";

const dom = (html: string) =>
  new DOMParser().parseFromString(html, "text/html");
const text = (html: string) =>
  dom(html).body.textContent!.replace(/\s+/g, " ").trim();
const links = (html: string) =>
  [...dom(html).querySelectorAll("a")].map((a) => a.getAttribute("href"));

describe("supporting-page source parity", () => {
  it.each(Object.keys(legal) as (keyof typeof legal)[])(
    "preserves all authored legal text and links: %s",
    (key) => {
      const original = renderOriginalLegal(key);
      expect(text(legal[key].html)).toBe(text(original));
      expect(links(legal[key].html)).toEqual(links(original));
      expect(legal[key].contents).toHaveLength(
        dom(original).querySelectorAll("h2").length,
      );
      expect(legal[key].sha256).toBe(
        createHash("sha256")
          .update(
            fs.readFileSync(path.resolve("../mouth", legalSourcePaths[key])),
          )
          .digest("hex"),
      );
      expect(legal[key].html).not.toMatch(
        /<(?:script|iframe|form)|\s(?:style|class|on\w+)=/i,
      );
      for (const section of legal[key].contents)
        expect(
          dom(legal[key].html).getElementById(section.id)?.textContent,
        ).toBe(section.title);
    },
  );
  it("keeps both distinct privacy artifacts and the four authored cookie records", () => {
    expect(text(legal.privacy.html)).not.toBe(text(legal["v2-privacy"].html));
    expect(legal.privacy.contents).toHaveLength(10);
    expect(legal["v2-privacy"].contents).toHaveLength(6);
    expect(
      dom(legal["v2-cookies"].html).querySelectorAll("tbody tr"),
    ).toHaveLength(4);
  });
  it("keeps the book's chapter, locale, contact and service identities against the canonical source", () => {
    const original = loadOriginalBook() as {
      CHAPTERS: { id: string }[];
      SERVICES: { serviceKey: string }[];
    };
    expect(book).toEqual(makeBookSnapshot());
    expect(book.chapters.map((chapter) => chapter.id)).toEqual(
      original.CHAPTERS.map((chapter: { id: string }) => chapter.id),
    );
    expect(Object.keys(book.locales)).toHaveLength(5);
    expect(bookServices()).toHaveLength(original.SERVICES.length);
    expect(bookServices().map((service) => service.serviceKey)).toEqual(
      original.SERVICES.map(
        (service: { serviceKey: string }) => service.serviceKey,
      ),
    );
    expect(
      bookServices().every(
        (service) =>
          service.scope.length && service.href.startsWith("/services"),
      ),
    ).toBe(true);
    expect(JSON.stringify(book)).not.toMatch(
      /"price"|9[,. ]612|No hallucinations|−8%/,
    );
  });
  it("preserves company copy with the declared owner-name privacy exception", () => {
    expect(company).toEqual(makeCompanySnapshot());
    expect(company.careers.paragraphs[0]).toContain(
      "We'll post open roles here when the time is right.",
    );
    expect(company.press.paragraphs[0]).toContain(
      "Our team is available for comment",
    );
    expect(company.press.paragraphs.at(-1)).toContain("one business day");
  });
  it("validates locale links and supplies native handlers for every owned route", () => {
    expect(bookLocale("it")).toBe("it");
    expect(bookLocale("../../etc")).toBe("en");
    expect(bookLocale(["zh", "it"])).toBe("zh");
    expect(bookHref("services", "ru")).toBe("/book/services?lang=ru");
    for (const route of [
      "privacy",
      "terms",
      "v2/privacy",
      "v2/terms",
      "v2/cookies",
      "v2/company/careers",
      "v2/company/press",
      "book",
      "book/[slug]",
    ]) {
      expect(fs.existsSync(path.join("src/app", route, "page.tsx"))).toBe(true);
      expect(fs.existsSync(path.join("src/app", route, "route.ts"))).toBe(
        false,
      );
    }
  });
});
