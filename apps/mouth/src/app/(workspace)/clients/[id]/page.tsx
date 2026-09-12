// Server boundary for the client detail page.
//
// The page is "use client" (tabs, forms, react-query), so its module constants —
// and its children's — ship to the browser. The tax-consultant table lived in
// `components/TaxTab.tsx` and put two staff names in this route's public chunk, an
// asset served without a session even though the page requires one. It is resolved
// here and threaded down instead.
//
// The route reads its own `id` through `useParams` on the client, so this wrapper
// forwards no ROUTE PARAMS. The one thing it does hold is the consultant table —
// which is the whole reason it exists, so do not trim it as dead server data.
import { taxConsultants } from "@/lib/workspace/roster-directory";
import ClientDetailClient from "./ClientDetailClient";

export default function ClientDetailPage() {
  return <ClientDetailClient taxConsultants={taxConsultants()} />;
}
