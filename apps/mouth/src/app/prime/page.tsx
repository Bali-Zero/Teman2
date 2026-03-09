import PrimeMap3D from "@/components/maps/PrimeMap3D";

export const metadata = {
  title: "Prime Intelligence — Bali Zoning Map",
  description:
    "Real-time GISTARU zoning intelligence for Bali property and business decisions.",
  robots: "noindex",
};

export default function PrimePage() {
  return (
    <main className="min-h-screen bg-slate-950 flex flex-col">
      <div className="flex-1 p-4">
        <PrimeMap3D />
      </div>
    </main>
  );
}
