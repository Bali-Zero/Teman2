export interface CatalogItem {
  code: string;
  title: string;
  titleId: string;
  section: string | null;
  sectionName: string | null;
  ownership: string;
  ownershipVerified: boolean;
  risks: string[];
  licensingPending: boolean;
  licensingInherited: string[];
  bali: string;
  licenses: string[];
  predecessorCodes: string[];
}

export interface ExplorerReply {
  answer: string;
  detected_kbli: string[];
  suggested_queries: string[];
  sources: { label: string; code?: string; content: string }[];
}
