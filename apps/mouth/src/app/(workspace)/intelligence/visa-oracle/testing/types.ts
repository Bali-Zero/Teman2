export type Expected = {
  text: string;
  basis: "hypothesis" | "official" | "expert" | "needs_review";
  reference: string;
  browser: string;
  device: string;
  displayed_version: string;
};
export type Result = {
  steps: string;
  actual_state:
    | "supported"
    | "needs_input"
    | "human_review"
    | "no_path"
    | "unavailable"
    | "blocked"
    | "other";
  actual: string;
  source_notes: string;
  uncertainty: string;
  comment: string;
  category:
    | "none"
    | "eligibility"
    | "missing_question"
    | "explanation"
    | "reference"
    | "navigation"
    | "privacy";
  severity: "none" | "low" | "medium" | "high";
  certainty: "observation" | "hypothesis" | "expert";
  reproducibility: "not_retried" | "same" | "different" | "blocked";
  evidence_ref: string;
  screenshot_base64?: string;
};
export type Review = {
  verdict: "confirmed_issue" | "not_issue" | "needs_expert_review";
  comment: string;
  reproduced: boolean;
  reproduction_evidence: string;
  reviewed_at?: string;
};
export type Assignment = {
  id: string;
  slot: string;
  day: string;
  index: number;
  can_start?: boolean;
  can_record_results: boolean;
  scenario: {
    id: string;
    title: string;
    focus: string;
    inputs: Record<string, string>;
    instructions: string[];
  };
  record: null | {
    status: "started" | "submitted";
    expected?: Expected;
    started_at: string;
    submitted_at: string | null;
    result?: (Partial<Result> & { screenshot_available?: boolean }) | null;
    review?: Review | null;
  };
};
export type CampaignData = {
  campaign: {
    id: string;
    start_date: string;
    end_date: string;
    timezone: string;
    planned: number;
    per_day: number;
    plan_version: string;
  };
  viewer: { slot: string | null; can_review: boolean; can_configure: boolean };
  slots: { slot: string; member_id: string | null; reviewer: boolean }[];
  staff_candidates?: { id: string; label: string }[];
  assignments: Assignment[];
  progress: {
    slot: string;
    day: string;
    planned: number;
    submitted: number;
    reviewed: number;
  }[];
  counts: {
    planned: number;
    started: number;
    submitted: number;
    reproduced: number;
    reviewed: number;
    reached: number;
    blocked: number;
  };
};
