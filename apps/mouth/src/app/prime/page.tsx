import PrimeMap3D from "@/components/maps/PrimeMap3D";

export const metadata = {
  title: "Prime Intelligence — Bali Zoning Map",
  description:
    "Real-time GISTARU zoning intelligence for Bali property and business decisions.",
  robots: "noindex",
};

export default function PrimePage() {
  return (
    <main className="h-screen bg-black overflow-hidden">
      <PrimeMap3D />
    </main>
  );
}
