export interface ConcordanceEntry {
  code: string;
  status: "REVOKED" | "CRITICAL" | "SPLIT" | "ELEVATED_RISK";
  reason: string;
  impact: string;
  action: string;
}

export const KBLI_CONCORDANCE_2025: Record<string, ConcordanceEntry> = {
  "63122": {
    code: "63122",
    status: "REVOKED",
    reason: "Digital Platforms catch-all has been terminated.",
    impact:
      "Digital Agencies, Portals, and Nomad hubs are now technically non-compliant.",
    action:
      "Requires split into specific codes for AI, Content, or Infrastructure.",
  },
  "56101": {
    code: "56101",
    status: "CRITICAL",
    reason: "Restructured F&B classification for Restaurants.",
    impact:
      "Small Cafés are being auto-migrated into Large Enterprise categories (10B IDR investment).",
    action: "Audit required to find the 'Small scale' sub-category successor.",
  },
  "55113": {
    code: "55113",
    status: "CRITICAL",
    reason: "Villa & Accommodation codes moved to high-risk scrutiny.",
    impact: "OTA (Airbnb/Booking) verification cutoff on March 31, 2026.",
    action: "Immediate Akta-OSS sync required to prevent listing delisting.",
  },
  "70209": {
    code: "70209",
    status: "REVOKED",
    reason: "Generic Management Consulting catch-all deleted.",
    impact:
      "Consulting firms must now specify their sector (IT, HR, Marketing, etc.).",
    action: "Requires Akta amendment to select valid 2025 successors.",
  },
  "62019": {
    code: "62019",
    status: "SPLIT",
    reason: "Other IT Activities split into AI and Cybersecurity.",
    impact:
      "High-tech companies need to align with new specific incentive-eligible codes.",
    action: "Update NIB to qualify for specific tech sector benefits.",
  },
  "68111": {
    code: "68111",
    status: "CRITICAL",
    reason:
      "Strict separation between Long-term Real Estate and Daily Rentals.",
    impact:
      "Using this code for daily guests (Airbnb) triggers automatic delisting by March 31.",
    action: "Migrate to 55203 (Villa) if providing hospitality services.",
  },
  "55209": {
    code: "55209",
    status: "ELEVATED_RISK",
    reason: "New operational restriction on housekeeping services.",
    impact:
      "Daily cleaning is strictly prohibited. Violations lead to NIB suspension.",
    action:
      "Audit service levels. Move to 55106 if high-touch service is required.",
  },
};
