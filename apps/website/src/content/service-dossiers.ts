import type { ServicePage } from "./service-pages";
import { dossierFamilies, dossierRecords, dossierSources } from "./service-dossier-data";

export type DossierSource = { label: string; url: string; checkedOn: string };
export type DossierFamily = {
  purpose: string; distinction: string; scope: readonly string[];
  preparation: readonly string[]; limit: string; next: string; source?: string;
};
export type DossierRecord = {
  id: string; name: string; domain: ServicePage["slug"]; family: string;
  route: "" | "onshore" | "offshore" | "renewal"; variant: string;
};
export type ServiceDossier = DossierRecord & Omit<DossierFamily, "source"> & {
  explanation: string; routeNote: string; variantNote: string;
  reference?: DossierSource; guide?: { href: string; label: string };
};

const routes = {
  onshore: {
    intro: "For an applicant already in Indonesia considering a change of status.",
    detail: "Altus means alih status, a change of status inside Indonesia. The current permit must support the proposed change; being onshore alone is not enough. An ordinary renewal is a separate service.",
    preparation: "Current permit, entry record and expiry date, plus the proposed new sponsor or status",
    next: "Confirm whether the present permit can be changed before it expires.",
  },
  offshore: {
    intro: "For an applicant outside Indonesia preparing a new entry application.",
    detail: "The offshore application is prepared before entry. It differs from an onshore change of status or renewal; sequence travel around the issued permission, not the submission date.",
    preparation: "Current country of residence, planned entry date and passport used for travel",
    next: "Confirm application readiness before finalising the intended entry date.",
  },
  renewal: {
    intro: "For a holder reviewing continuation of an existing permit.",
    detail: "An extension starts from the existing permit and its expiry. A change of purpose or sponsor may require a different process; the renewal label does not guarantee continuation or a particular term.",
    preparation: "Existing permit and expiry, previous extensions and any change in sponsor or activities",
    next: "Check the existing permit and any changed circumstances before the renewal window closes.",
  },
} as const;

function compose(record: DossierRecord): ServiceDossier {
  const family: DossierFamily = dossierFamilies[record.family as keyof typeof dossierFamilies];
  const route = record.route ? routes[record.route] : undefined;
  const term = record.variant.toLowerCase();
  const variantNote = !term ? "" : record.family === "urgent"
    ? `Requested turnaround: ${term}. Availability must be confirmed for the underlying application.`
    : ["d1", "d2", "d12"].includes(record.family)
      ? `Requested multiple-entry validity: ${term}. This is not a continuous stay of ${term}; confirm availability and the limit on each visit.`
      : record.family === "passport"
        ? `Requested format: ${record.name.startsWith("Electronic") ? "electronic" : "ordinary"}; requested validity: ${term}. Confirm issuance options for the applicant’s age and circumstances.`
        : `Requested period: ${term}. The current route, supporting documents and issued permission determine the term actually available.`;
  return {
    ...family, ...record,
    explanation: [family.purpose, route?.intro, variantNote].filter(Boolean).join(" "),
    routeNote: route?.detail ?? "", variantNote,
    preparation: [...family.preparation, ...(route ? [route.preparation] : [])],
    next: [family.next, route?.next].filter(Boolean).join(" "),
    reference: family.source ? dossierSources[family.source as keyof typeof dossierSources] : undefined,
    ...(record.family === "secondhome" ? { guide: { href: "/visa/second-home", label: "Read the Second Home guide" } } : {}),
  };
}

export const serviceDossiers: readonly ServiceDossier[] = dossierRecords.map(compose);
const dossiersByName = new Map(serviceDossiers.map((dossier) => [dossier.name, dossier]));

export function getServiceDossier(name: string): ServiceDossier {
  const dossier = dossiersByName.get(name);
  if (!dossier) throw new Error(`Missing editorial dossier: ${name}`);
  return dossier;
}
