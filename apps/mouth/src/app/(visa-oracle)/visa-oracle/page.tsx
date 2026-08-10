import { cookies } from "next/headers";
import { OracleShell } from "./_components/OracleShell";
import {
  INTERNAL_ACCESS_COOKIE,
  verifyInternalAccessToken,
} from "./_lib/internal-access";

/**
 * Reading the internal-access cookie opts this route into per-request
 * rendering. That is deliberate: deciding on the SERVER is what makes the
 * gate unforgeable (a client-side probe would either race the interview or
 * be patchable in the browser), and the page's work is client-side anyway,
 * so the server render stays cheap.
 */
export const dynamic = "force-dynamic";

export default async function VisaOraclePage() {
  const cookieStore = await cookies();
  const internalMode = verifyInternalAccessToken(
    cookieStore.get(INTERNAL_ACCESS_COOKIE)?.value,
  );

  return <OracleShell internalMode={internalMode} />;
}
