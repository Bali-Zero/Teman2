import { permanentRedirect } from "next/navigation";
import { forwardSearchParams } from "../../../lib/forward-search-params";

export default async function LegacyCompanyRoute({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  permanentRedirect(
    `/services/company-setup${forwardSearchParams((await searchParams) ?? {})}`,
  );
}
