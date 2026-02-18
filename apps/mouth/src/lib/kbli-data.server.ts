// KBLI Data Server - Stub for build
export interface KBLICode {
  code: string;
  name: string;
  description?: string;
  section?: string;
  pma?: { status: string };
  transition?: { status: string };
}

export interface KBLISection {
  code: string;
  name: string;
  description?: string;
}

export function getSections(): KBLISection[] {
  return [
    { code: "A", name: "Agriculture", description: "" },
    { code: "B", name: "Mining", description: "" },
    { code: "C", name: "Manufacturing", description: "" },
    { code: "D", name: "Electricity", description: "" },
    { code: "E", name: "Water Supply", description: "" },
    { code: "F", name: "Construction", description: "" },
    { code: "G", name: "Trade", description: "" },
    { code: "H", name: "Transportation", description: "" },
    { code: "I", name: "Accommodation", description: "" },
    { code: "J", name: "Information", description: "" },
  ];
}

export function getAllCodes(): KBLICode[] {
  // Return some dummy codes with proper structure
  return [
    {
      code: "56101",
      name: "Restaurant",
      description: "Restaurant activities",
      pma: { status: "open" },
      transition: { status: "MATCH" },
    },
    {
      code: "55194",
      name: "Hotel",
      description: "Hotel activities",
      pma: { status: "open" },
      transition: { status: "MATCH" },
    },
    {
      code: "62011",
      name: "Software Development",
      description: "Computer programming",
      pma: { status: "open" },
      transition: { status: "BPS_ONLY" },
    },
    {
      code: "68110",
      name: "Real Estate",
      description: "Buying and selling of real estate",
      pma: { status: "restricted" },
      transition: { status: "MATCH_CON_AGGREGAZIONE" },
    },
  ];
}

export function getCodesBySection(_section: string): KBLICode[] {
  return [];
}

export function getCodeById(_id: string): KBLICode | null {
  return null;
}

export function searchKBLI(_query: string): KBLICode[] {
  return [];
}
