"use client";

import { useParams } from "next/navigation";
import { CheckoutFlow } from "./CheckoutFlow";

/**
 * `/visa/voa/checkout/{resultId}` — customer-facing checkout step (L4 part 3).
 * `resultId` is the same opaque eligibility-check id `upload/{resultId}` uses.
 */
export default function CheckoutPage() {
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

  return <CheckoutFlow resultId={resultId} />;
}
