"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { UserPlus } from "lucide-react";

import { api } from "@/lib/api";

/**
 * Persistent "contacts to name" banner.
 *
 * WA-mirror auto-creates a phone-keyed lead (`Lead +628…`) the first time a new
 * contact sends a document. Until an operator gives it a real name, every
 * document from that contact lands as NO_MATCH/LINK_CANDIDATE in review instead
 * of attaching to a named client. This banner is the persistent, non-blocking
 * nudge: it shows the count of still-unnamed leads (scoped by RBAC to the
 * operator's own clients) and links to the filtered list. It renders nothing
 * when there is nothing to name, so it never adds noise on a clean book.
 *
 * The backend `unnamed=true` filter mirrors the placeholder-name patterns in
 * apps/wa-dashboard-m1/server.cjs so both surfaces agree on "needs a name".
 */
export default function UnnamedLeadsBanner() {
  const { data: unnamed } = useQuery({
    queryKey: ["clients", "unnamed"],
    queryFn: () => api.crm.getClients({ unnamed: true, limit: 200 }),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const count = unnamed?.length ?? 0;
  if (count === 0) return null;

  return (
    <Link
      href="/clients?unnamed=1"
      className="flex items-center gap-3 rounded-lg px-4 py-3 transition-colors"
      style={{
        background: "rgba(212, 132, 90, 0.12)",
        border: "1px solid rgba(212, 132, 90, 0.35)",
      }}
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
        style={{ background: "rgba(212, 132, 90, 0.22)" }}
      >
        <UserPlus className="h-4 w-4" style={{ color: "#d4845a" }} />
      </span>
      <span className="text-sm">
        <span className="font-semibold" style={{ color: "#d4845a" }}>
          {count} {count === 1 ? "contact" : "contacts"} to name
        </span>
        <span className="ml-2 text-[var(--foreground-muted)]">
          — new WhatsApp leads without a name. Name them so their documents
          link automatically.
        </span>
      </span>
    </Link>
  );
}
