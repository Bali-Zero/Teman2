import type { Metadata } from "next";
import { describe, expect, it } from "vitest";
import { journalCategories } from "../content/journal-categories";
import { getAllCodes, getSections } from "../features/kbli/catalog.server";
import { metadata as rootMetadata } from "./layout";
import { metadata as homeMetadata } from "./page";
import { generateMetadata as categoryMetadata } from "./[category]/page";
import { generateMetadata as sectorMetadata } from "./kbli/sectors/[id]/page";
import { generateMetadata as codeMetadata } from "./kbli/[code]/page";
import { metadata as newsMetadata } from "./news/page";
import { metadata as proposalMetadata } from "./prime/proposal/[token]/page";
import { metadata as oracleMetadata } from "./visa-oracle/page";
import { metadata as unlockMetadata } from "./visa-oracle/unlock/layout";
import { metadata as oraclePrivacyMetadata } from "./visa-oracle/privacy/layout";
import { metadata as clockMetadata } from "./visa/clock/[hash]/page";
import { metadata as matchMetadata } from "./visa/match/[hash]/page";
import { metadata as visaPrivacyMetadata } from "./visa/privacy/page";
import { metadata as visaTermsMetadata } from "./visa/terms/page";
import { metadata as voaMetadata } from "./visa/voa/page";
import { metadata as primeMetadata } from "./prime/page";
import { metadata as cookiesMetadata } from "./v2/cookies/page";
import { metadata as careersMetadata } from "./v2/company/careers/page";
import { metadata as pressMetadata } from "./v2/company/press/page";
import { metadata as privacyMetadata } from "./v2/privacy/page";
import { metadata as termsMetadata } from "./v2/terms/page";

function expectNoIndex(metadata: Metadata): void {
  expect(metadata.robots).toMatchObject({ index: false, follow: false });
}

function expectMetadata(
  metadata: Metadata,
  canonical: string,
  title?: string,
): void {
  expect(metadata.title).not.toBe("Bali Zero — Website development");
  if (title) expect(metadata.title).toBe(title);
  expect(metadata.description).toEqual(expect.any(String));
  expect(metadata.alternates?.canonical).toBe(canonical);
}

describe("cutover metadata", () => {
  it("removes the global noindex and publishes the approved root title without a duplicate suffix template", () => {
    expect(rootMetadata.robots).toBeUndefined();
    expect(rootMetadata.title).toBe(
      "Bali Zero | Immigration, Company Setup, Tax & Property in Indonesia",
    );
  });

  it("keeps explicit noindex on every private or retained route", () => {
    for (const metadata of [
      unlockMetadata,
      oraclePrivacyMetadata,
      voaMetadata,
      primeMetadata,
      careersMetadata,
      pressMetadata,
      privacyMetadata,
      termsMetadata,
      cookiesMetadata,
      visaPrivacyMetadata,
      visaTermsMetadata,
      proposalMetadata,
      matchMetadata,
      clockMetadata,
    ]) {
      expectNoIndex(metadata);
    }
  });

  it("fills static homepage, News and Visa Oracle metadata gaps", () => {
    expectMetadata(homeMetadata, "/", "Bali Zero Indonesia | Bali Zero");
    expectMetadata(newsMetadata, "/news", "The Bali Zero Journal | Bali Zero");
    expectMetadata(oracleMetadata, "/visa-oracle", "Visa Oracle | Bali Zero");
    expect(oracleMetadata.robots).toBeUndefined();
  });

  it("derives category metadata from the canonical category registry", async () => {
    for (const category of journalCategories) {
      expectMetadata(
        await categoryMetadata({
          params: Promise.resolve({ category: category.slug }),
        }),
        `/${category.slug}`,
        `${category.label} | Bali Zero`,
      );
    }
  });

  it("derives KBLI section and code metadata from the catalog", async () => {
    const section = getSections()[0];
    const code = getAllCodes()[0];

    expectMetadata(
      await sectorMetadata({ params: Promise.resolve({ id: section.id }) }),
      `/kbli/sectors/${section.id}`,
      `${section.nameEn} KBLI sector | Bali Zero`,
    );
    const metadata = await codeMetadata({
      params: Promise.resolve({ code: code.code }),
    });
    expectMetadata(metadata, `/kbli/${code.code}`);
    expect(metadata.description).toContain(code.titleEn);
  });
});
