import { permanentRedirect } from "next/navigation";

export default function LegacyVisaRoute() {
  permanentRedirect("/services/immigration");
}
