"use client";

import useSWR, { type SWRResponse } from "swr";
import { api } from "@/lib/api";
import { VaultListResponse, type VaultFile } from "@/lib/schemas/vault";

type HttpError = { status?: number };

/**
 * SWR hook for `GET /api/portal/documents`.
 *
 * Fetches the raw envelope `{ success, data }` and validates it with Zod
 * before returning the inner `data` array. Schema drift or `success: false`
 * surface as SWR errors rather than partial UI.
 *
 * Note: the list endpoint does NOT expose `scan_status`. Scan results are
 * only emitted (as `processing.virus_clean`) by the upload endpoint — see
 * `useVaultUpload`.
 */
export function useVaultFiles(): SWRResponse<VaultFile[], Error> {
  return useSWR<VaultFile[], Error>(
    ["portal-vault-files"],
    async () => {
      const raw = await api.get<unknown>("/api/portal/documents");
      const parsed = VaultListResponse.parse(raw);
      if (!parsed.success) {
        const err = new Error("Vault response not successful");
        (err as HttpError).status = 500;
        throw err;
      }
      return parsed.data;
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 5000,
      shouldRetryOnError: (err: { status?: number } | Error) => {
        const status = (err as { status?: number })?.status ?? 0;
        return status >= 500;
      },
    },
  );
}
