import type { Metadata } from "next";
import { StudioApp } from "./StudioApp";

/**
 * Second Home Studio — public, anonymous fit-check wizard (Phase B).
 *
 * Thin SERVER shell: metadata only. All interactivity lives in StudioApp
 * ("use client"). No `robots` override — this route is index/follow like
 * its parent landing (spec §1/§7.7).
 */
export const metadata: Metadata = {
  title: "Second Home Studio — check your fit",
  description:
    "A free, anonymous fit-check for Indonesia's Second Home Visa (E33). Answer a few questions, see your fit-check result, and get a plan you can save or share — no email needed.",
  openGraph: {
    title: "Second Home Studio — Bali Zero",
    description:
      "Check your fit for Indonesia's Second Home Visa in a few minutes. Free, anonymous, no email needed.",
    type: "website",
  },
  alternates: {
    canonical: "https://balizero.com/visa/second-home/studio",
  },
};

export default function SecondHomeStudioPage() {
  return <StudioApp />;
}
