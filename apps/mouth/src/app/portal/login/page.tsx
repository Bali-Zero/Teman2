import { permanentRedirect } from "next/navigation";
import { sanitizeRedirect } from "@/lib/auth/sanitizeRedirect";

interface Props {
  searchParams: Promise<{ redirect?: string }> | { redirect?: string };
}

export default async function LegacyLoginRedirect({ searchParams }: Props) {
  const params = await searchParams;
  const safe = sanitizeRedirect(params.redirect);
  const qs = safe ? `?redirect=${encodeURIComponent(safe)}` : "";
  permanentRedirect(`/portal/login-upgraded${qs}`);
}
