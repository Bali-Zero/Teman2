// Tax content cluster mapping — sourced from docs/marketing/spec-tax.md §3+§5
// Consumed by ArticleClusterCTA component (Subhi D2 Minggu 3 deliverable).

import c1 from "./c1-tax-residency.json";
import c2 from "./c2-npwp-coretax.json";
import c3 from "./c3-incentives-holiday.json";
import c4 from "./c4-rental-property.json";
import c5 from "./c5-deadlines-filing.json";
import c6 from "./c6-vat-ppn.json";

export type ArticleRef = {
  slug: string;
  category: string;
  title: string;
};

export type ToCreateRef = {
  slug: string;
  category: string;
  rationale: string;
  priority: "high" | "medium" | "low";
};

export type Cluster = {
  id: string;
  title: string;
  intent: string;
  pillar: ArticleRef;
  spokes: ArticleRef[];
  to_create?: ToCreateRef[];
  cannibalization_note?: string;
  related_clusters: string[];
};

export const CLUSTERS: Record<string, Cluster> = {
  "c1-tax-residency": c1 as Cluster,
  "c2-npwp-coretax": c2 as Cluster,
  "c3-incentives-holiday": c3 as Cluster,
  "c4-rental-property": c4 as Cluster,
  "c5-deadlines-filing": c5 as Cluster,
  "c6-vat-ppn": c6 as Cluster,
};

export function getCluster(id: string): Cluster | undefined {
  return CLUSTERS[id];
}

export function getAllClusters(): Cluster[] {
  return Object.values(CLUSTERS);
}

export function findClusterBySlug(slug: string): Cluster | undefined {
  for (const cluster of Object.values(CLUSTERS)) {
    if (cluster.pillar.slug === slug) return cluster;
    if (cluster.spokes.some((s) => s.slug === slug)) return cluster;
  }
  return undefined;
}
