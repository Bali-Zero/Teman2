"use client";

import { useParams } from "next/navigation";
import { OrderTracker } from "../OrderTracker";

/**
 * `/visa/voa/orders/{orderId}` — the customer-facing parcel tracker and (once
 * `practice.state === "Delivered"`) visa delivery view. `orderId` is the opaque order
 * identifier from `createOrderFromCheck` (`OrderCheckout.order_id` /
 * `OpaqueId` in the contract) — never a raw database id.
 */
export default function OrderPage() {
  const params = useParams<{ orderId: string }>();
  const orderId = params?.orderId;

  if (!orderId) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-gray-600">
          We couldn&apos;t find this order. Please check the link.
        </p>
      </main>
    );
  }

  return <OrderTracker orderId={orderId} />;
}
