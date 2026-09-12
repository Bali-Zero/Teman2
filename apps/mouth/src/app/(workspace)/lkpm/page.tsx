// Server boundary for the LKPM batch page.
//
// The page itself is "use client" (forms, toasts, local state), so anything it
// holds as a module constant ships to the browser. The tax-consultant table used
// to live there and put staff names in this route's public chunk; it is resolved
// here instead and handed down as a prop.
import { taxConsultants } from "@/lib/workspace/roster-directory";
import LkpmBatchClient from "./LkpmBatchClient";

export default function LKPMBatchPage() {
  return <LkpmBatchClient taxConsultants={taxConsultants()} />;
}
