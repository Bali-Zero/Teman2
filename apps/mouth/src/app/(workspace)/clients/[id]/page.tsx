// Server boundary for the client detail page.
//
// Same shape as `(workspace)/lkpm/page.tsx`, and for the same reason. The page
// body is "use client" — tabs, modals, mutations, local state — so every module
// constant it holds is compiled into this route's static chunk, and a Next static
// chunk is served from the CDN path with NO session. The tax-consultant table
// used to be such a constant in `components/TaxTab.tsx`, which is how an
// anonymous GET of
// `/_next/static/chunks/app/(workspace)/clients/%5Bid%5D/page-*.js`
// returned a name the owner had excluded from public surfaces.
//
// Resolving it here moves those addresses out of the chunk and into this route's
// server payload. That is a real improvement and not a complete fix: the payload
// is still sent before `(workspace)/layout.tsx` gates the viewer, because that
// gate is client-side. That residual is tracked as its own piece of work and is
// deliberately NOT addressed here.
import { taxConsultants } from "@/lib/workspace/roster-directory";
import { ClientDetailClient } from "./ClientDetailClient";

export default function ClientDetailPage() {
  return <ClientDetailClient taxConsultants={taxConsultants()} />;
}
