import Link from "next/link";

export default function KBLINotFound() {
  return (
    <div className="py-20 text-center">
      <h1 className="text-4xl font-bold text-[var(--foreground)]">
        Code Not Found
      </h1>
      <p className="mt-4 text-[var(--foreground-secondary)]">
        This KBLI code doesn&apos;t exist in the 2025 classification. It may
        have been renumbered or merged.
      </p>
      <div className="mt-8 flex justify-center gap-4">
        <Link
          href="/kbli"
          className="rounded-lg bg-[var(--kbli-accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Search All Codes
        </Link>
        <Link
          href="/kbli/sectors"
          className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--foreground-secondary)] hover:text-[var(--foreground)]"
        >
          Browse by Sector
        </Link>
      </div>
    </div>
  );
}
