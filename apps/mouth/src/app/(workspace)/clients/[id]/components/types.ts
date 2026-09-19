"use client";

// The one list of tab keys. TabType and the `?tab=` reader both derive from it,
// so a tab the page can write into the URL is always a tab it can read back.
export const TAB_KEYS = [
  "overview",
  "documents",
  "process",
  "family",
  "visas",
  "company",
  "tax",
  "timeline",
  "whatsapp",
] as const;

export type TabType = (typeof TAB_KEYS)[number];

export function isTabType(value: string | null | undefined): value is TabType {
  return (TAB_KEYS as readonly string[]).includes(value ?? "");
}

export type ModalType =
  | "none"
  | "edit_client"
  | "add_family"
  | "edit_family"
  | "add_document"
  | "edit_document";
