export const journalCategories = [
  { slug: "visas", label: "Visas" },
  { slug: "business", label: "Business" },
  { slug: "taxes", label: "Taxes" },
  { slug: "property", label: "Property" },
  { slug: "living", label: "Living" },
  { slug: "trends", label: "Tech & Trends" },
] as const;

export type JournalCategory = typeof journalCategories[number]["slug"];
export function isJournalCategory(value: string): value is JournalCategory {
  return journalCategories.some((category) => category.slug === value);
}
