import {
  isLoopback,
  oracleBackendUrl,
} from "../../features/visa-oracle/evaluate.server";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { OracleShell } from "../../features/visa-oracle/_components/OracleShell";
import {
  INTERNAL_ACCESS_COOKIE,
  verifyInternalAccessToken,
} from "../../features/visa-oracle/_lib/internal-access";

/**
 * Reading the internal-access cookie opts this route into per-request
 * rendering. That is deliberate: deciding on the SERVER is what makes the
 * gate unforgeable (a client-side probe would either race the interview or
 * be patchable in the browser), and the page's work is client-side anyway,
 * so the server render stays cheap.
 */
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Visa Oracle | Bali Zero",
  description:
    "Explore a guided visa assessment for living, working and investing in Indonesia.",
  alternates: { canonical: "/visa-oracle" },
};

export default async function VisaOraclePage() {
  const cookieStore = await cookies();
  const internalMode = verifyInternalAccessToken(
    cookieStore.get(INTERNAL_ACCESS_COOKIE)?.value,
  );

  const backend = oracleBackendUrl(process.env.WEBSITE_VISA_ORACLE_BACKEND_URL);
  const local = backend !== null && isLoopback(backend);
  const localProof =
    local && process.env.WEBSITE_VISA_ORACLE_LOCAL_PROOF === "unsigned-proposal"
      ? "unsigned-proposal"
      : local;
  return <OracleShell internalMode={internalMode} localProof={localProof} />;
}
