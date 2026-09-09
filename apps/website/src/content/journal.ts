export type JournalVerificationStatus =
  | "pending"
  | "verified"
  | "unavailable"
  | "development-only";

export interface JournalImage {
  readonly src: string;
  readonly alt: string;
  readonly sourceSrc?: string;
}

export interface JournalDate {
  readonly iso: string;
  readonly label: string;
}

export interface JournalArticle {
  readonly title: string;
  readonly slug: string;
  readonly image: JournalImage | null;
  readonly category: string | null;
  readonly date: JournalDate | null;
  readonly sourceUrl: string;
  readonly finalSourceUrl: string | null;
  readonly verificationStatus: JournalVerificationStatus;
  readonly localHref?: string;
  readonly summary?: string;
  readonly featured?: boolean;
  readonly reading?: {
    readonly author?: { readonly name: string; readonly role?: string };
    readonly reviewedBy?: string;
    readonly updated?: JournalDate;
    readonly minutes?: number;
    readonly aiGenerated?: boolean;
    readonly disclosure?: string;
  };
  readonly editorial?: {
    readonly summary: string;
    readonly whyItMatters: string;
    readonly revision: number;
    readonly amended: boolean;
    readonly updatedAt: JournalDate;
    readonly evidence: readonly { publisher: string; citation: string | null; url: string | null }[];
    readonly revisions: readonly { version: number; publishedAt: JournalDate }[];
  };
}

export interface JournalArticleSection {
  readonly heading: string;
  readonly paragraphs: readonly string[];
}

export interface JournalArticleDocument {
  readonly metadata: JournalArticle;
  readonly standfirst: string;
  readonly sections: readonly JournalArticleSection[];
  readonly indexing: "excluded" | "public";
  readonly markdown?: string;
}

/**
 * The source records are a direct inventory of the six stories already present
 * in the approved R19 homepage. A record is not public on /journal until its
 * destination has been checked and its status has been changed to `verified`.
 */
export const journalArticleRecords: readonly JournalArticle[] = [
  {
    title:
      "Bali's Sub-$50K Villa Boom: Accessible Luxury or Due-Diligence Trap?",
    slug: "balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap",
    image: {
      src: "/assets/villa.jpg",
      alt: "Published cover for the Bali villa due-diligence story",
    },
    category: "Business",
    date: { iso: "2026-09-04", label: "4 September 2026" },
    sourceUrl:
      "https://balizero.com/business/balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap",
    finalSourceUrl:
      "https://balizero.com/business/balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap",
    verificationStatus: "verified",
  },
  {
    title: "The Villa Dream Has a New Wall (KBLI 55203)",
    slug: "the-villa-dream-has-a-new-wall",
    image: {
      src: "/assets/villa-wall.png",
      alt: "Published cover for The Villa Dream Has a New Wall",
    },
    category: "Business",
    date: { iso: "2026-06-23", label: "23 June 2026" },
    sourceUrl: "https://balizero.com/business/the-villa-dream-has-a-new-wall",
    finalSourceUrl:
      "https://balizero.com/business/the-villa-dream-has-a-new-wall",
    verificationStatus: "verified",
  },
  {
    title:
      "Indonesia's KBLI 2025 Shake-Up: The Transition Rules Every Business Must Know",
    slug:
      "indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know",
    image: {
      src: "/assets/kbli.jpg",
      alt: "Published cover for the KBLI 2025 transition story",
    },
    category: "Business",
    date: { iso: "2026-09-04", label: "4 September 2026" },
    sourceUrl:
      "https://balizero.com/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know",
    finalSourceUrl:
      "https://balizero.com/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know",
    verificationStatus: "verified",
  },
  {
    title: "The IT Escape Route",
    slug: "the-it-escape-route",
    image: {
      src: "/assets/it.png",
      alt: "Published cover for The IT Escape Route",
    },
    category: "Business",
    date: { iso: "2026-06-23", label: "23 June 2026" },
    sourceUrl: "https://balizero.com/business/the-it-escape-route",
    finalSourceUrl: "https://balizero.com/business/the-it-escape-route",
    verificationStatus: "verified",
  },
  {
    title: "Bali Immigration Brings Permit Services to Discovery Mall",
    slug: "bali-immigration-brings-permit-services-to-discovery-mall",
    image: {
      src: "/assets/immigration.jpg",
      alt: "Published cover for the Discovery Mall immigration story",
    },
    category: "Visas",
    date: { iso: "2026-07-11", label: "11 July 2026" },
    sourceUrl:
      "https://balizero.com/visas/bali-immigration-brings-permit-services-to-discovery-mall",
    finalSourceUrl:
      "https://balizero.com/visas/bali-immigration-brings-permit-services-to-discovery-mall",
    verificationStatus: "verified",
  },
  {
    title: "Indonesia's NIB: The One Business ID Every Investor Must Have",
    slug: "indonesias-nib-the-one-business-id-every-investor-must-have",
    image: {
      src: "/assets/nib.jpg",
      alt: "Published cover for the NIB business registration story",
    },
    category: "Business",
    date: { iso: "2026-07-11", label: "11 July 2026" },
    sourceUrl:
      "https://balizero.com/business/indonesias-nib-the-one-business-id-every-investor-must-have",
    finalSourceUrl:
      "https://balizero.com/business/indonesias-nib-the-one-business-id-every-investor-must-have",
    verificationStatus: "verified",
  },
] as const;

export function isPublicJournalArticle(
  article: JournalArticle,
): article is JournalArticle & { verificationStatus: "verified" } {
  return article.verificationStatus === "verified";
}

export function getPublicJournalArticles(): readonly JournalArticle[] {
  return journalArticleRecords.filter(isPublicJournalArticle);
}

/**
 * This synthetic document exists only to exercise the reusable article
 * template. It is not part of journalArticleRecords, is never returned by the
 * public selector and has no route or index entry.
 */
export const developmentOnlyArticleFixture: JournalArticleDocument = {
  metadata: {
    title: "Development fixture — Journal article template",
    slug: "development-fixture-journal-article",
    image: {
      src: "/assets/villa.jpg",
      alt: "Development-only editorial template fixture",
    },
    category: "Development fixture",
    date: null,
    sourceUrl: "https://example.invalid/development-fixture",
    finalSourceUrl: null,
    verificationStatus: "development-only",
  },
  standfirst:
    "This synthetic copy verifies layout and semantics. It is not editorial content.",
  sections: [
    {
      heading: "Template section",
      paragraphs: [
        "A real article may replace this fixture only after its complete content and source contract are authorized.",
      ],
    },
  ],
  indexing: "excluded",
};
