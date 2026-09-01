"use client";

import { useParams, useRouter } from "next/navigation";
import { UploadFlow } from "../UploadFlow";
import { writeCheckoutHandoff } from "../../checkoutHandoff";

/**
 * `/visa/voa/upload/{resultId}` — customer-facing document upload step (L5 owns this
 * route + everything under `upload/`; the rest of `/visa/voa/**` is L6's, blocked on
 * owner decision 5 for visual identity). `resultId` is the opaque eligibility-check id
 * from the funnel (`GARUDA VOA API` `ResultId` parameter) — never a raw database id, per
 * the binding persistence design (`research/visa/2026-08-23-voa-public-funnel-persistence-design.md`).
 *
 * `onConfirmed` bridges to checkout (L4 part 3, `../checkoutHandoff.ts` +
 * `../checkout/{resultId}`): it stashes the two `Applicant` fields checkout needs that
 * upload already collected (`full_name`, `passport_number`) client-side only, then
 * navigates forward. `UploadFlow` itself stays unaware of order/payment state — see its
 * own header comment.
 */
export default function UploadPage() {
  const params = useParams<{ resultId: string }>();
  const router = useRouter();
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

  return (
    <UploadFlow
      resultId={resultId}
      onConfirmed={(values) => {
        writeCheckoutHandoff(resultId, values);
        router.push(`/visa/voa/checkout/${resultId}`);
      }}
    />
  );
}
