import { permanentRedirect } from "next/navigation";
import { forwardSearchParams } from "../../../lib/forward-search-params";

export default async function LegacyVisaRoute({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  permanentRedirect(
    `/services/immigration${forwardSearchParams((await searchParams) ?? {})}`,
  );
}
