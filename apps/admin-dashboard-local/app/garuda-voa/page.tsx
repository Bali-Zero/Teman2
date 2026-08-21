import type { Metadata } from "next";
import { PinGate } from "@/components/cockpit/PinGate";
import { GarudaPreviewClient } from "./GarudaPreviewClient";
import "./garuda-preview.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "GARUDA VOA internal preview",
  description: "Owner-only synthetic GARUDA VOA pre-screen workbench.",
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false, noimageindex: true },
  },
};

export default function GarudaVoaInternalPage() {
  return (
    <PinGate>
      <GarudaPreviewClient />
    </PinGate>
  );
}
