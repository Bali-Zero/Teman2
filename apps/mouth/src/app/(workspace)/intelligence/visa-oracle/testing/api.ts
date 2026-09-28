import { api } from "@/lib/api";
import type { CampaignData, Expected, Result, Review } from "./types";
const RESULT_KEYS: (keyof Result)[] = [
  "steps",
  "actual_state",
  "actual",
  "source_notes",
  "uncertainty",
  "comment",
  "category",
  "severity",
  "certainty",
  "reproducibility",
  "evidence_ref",
  "screenshot_base64",
];
const ROOT = "/api/visa-oracle/testing";
const write = (path: string, method: string, body: unknown) =>
  api.request<{ ok: boolean }>(`${ROOT}${path}`, {
    method,
    body: JSON.stringify(body),
  });
export const testingApi = {
  load: () => api.request<CampaignData>(ROOT),
  start: (id: string, body: Expected) =>
    write(`/${encodeURIComponent(id)}/start`, "POST", {
      ...body,
      synthetic_only: true,
    }),
  result: (id: string, body: Partial<Result>, submit: boolean) =>
    write(`/${encodeURIComponent(id)}/result`, "PUT", {
      ...Object.fromEntries(
        RESULT_KEYS.filter((key) => body[key] !== undefined).map((key) => [
          key,
          body[key],
        ]),
      ),
      submit,
      synthetic_only: true,
    }),
  review: (id: string, body: Review) =>
    write(`/${encodeURIComponent(id)}/review`, "PATCH", body),
  slot: (slot: string, member_id: string | null, reviewer: boolean) =>
    write(`/slots/${encodeURIComponent(slot)}`, "PUT", { member_id, reviewer }),
  removeScreenshot: (id: string) =>
    write(`/${encodeURIComponent(id)}/screenshot`, "DELETE", undefined),
  export: () => api.request<CampaignData>(`${ROOT}/export`),
};
