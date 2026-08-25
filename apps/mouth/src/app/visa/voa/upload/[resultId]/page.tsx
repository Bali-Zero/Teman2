"use client";

import { useParams } from "next/navigation";
import { UploadFlow } from "../UploadFlow";

/**
 * `/visa/voa/upload/{resultId}` — customer-facing document upload step (L5 owns this
 * route + everything under `upload/`; the rest of `/visa/voa/**` is L6's, blocked on
 * owner decision 5 for visual identity). `resultId` is the opaque eligibility-check id
 * from the funnel (`GARUDA VOA API` `ResultId` parameter) — never a raw database id, per
 * the binding persistence design (`research/visa/2026-08-23-voa-public-funnel-persistence-design.md`).
 */
export default function UploadPage() {
  const params = useParams<{ resultId: string }>();
  const resultId = params?.resultId;

  if (!resultId) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-gray-600">
          We couldn&apos;t find your application. Please start again.
        </p>
      </main>
    );
  }

  return <UploadFlow resultId={resultId} />;
}
