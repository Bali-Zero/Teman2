import type { Metadata } from "next";
import { ServicesOverview } from "../../components/services/ServiceJourneys";

export const metadata: Metadata = {
  title: "Services | Bali Zero",
  description:
    "Explore Bali Zero support for immigration, company setup, tax and property decisions in Indonesia.",
};

export default function ServicesPage() {
  return <ServicesOverview />;
}
