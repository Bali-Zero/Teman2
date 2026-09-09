import { permanentRedirect } from "next/navigation";

export default function LegacyCompanyRoute() {
  permanentRedirect("/services/company-setup");
}
