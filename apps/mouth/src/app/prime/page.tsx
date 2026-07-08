import type { Metadata } from "next";
import PrimeNexusLayout from "@/components/maps/prime/PrimeNexusLayout";

export const metadata: Metadata = {
  title: "Prime Nexus — Bali Geospatial Decision Hub",
  description:
    "Real-time zoning intelligence, investment analysis, and CRM overlay for Bali property and business decisions.",
  robots: { index: false, follow: false },
};

export default function PrimePage() {
  return <PrimeNexusLayout />;
}
