"use client";

import { useState, useEffect } from "react";
import {
  Users,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Mail,
} from "lucide-react";
import { Button, Badge } from "@/components/ui/primitives";
import { InviteClientButton } from "@/components/InviteClientButton";
import { logger } from "@/lib/logger";

interface ClientRow {
  id: number;
  full_name?: string;
  email?: string;
  phone?: string;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const fetchClients = async (p = 1) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/postgres/query?table=clients&page=${p}`);
      const data = await res.json();
      setClients(data.rows ?? []);
    } catch (e) {
      logger.error("Failed to fetch clients:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients(page);
  }, [page]);

  const filtered = search.trim()
    ? clients.filter((c) => {
        const q = search.toLowerCase();
        return (
          c.full_name?.toLowerCase().includes(q) ||
          c.email?.toLowerCase().includes(q) ||
          String(c.id).includes(q)
        );
      })
    : clients;

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="border-b p-4 flex items-center justify-between bg-background">
        <div className="flex items-center gap-3">
          <Users className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-xl font-bold tracking-tight">Clients</h1>
            <p className="text-xs text-muted-foreground">
              Manage portal invitations for clients
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              className="bg-background border rounded-md pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none w-64"
              placeholder="Search by name, email, or ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchClients(page)}
          >
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
          <div className="flex items-center gap-1 border rounded-md">
            <Button
              variant="ghost"
              size="icon"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm px-2 min-w-[3rem] text-center">
              Pg {page}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Loading clients...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            {search ? "No clients match your search." : "No clients found."}
          </div>
        ) : (
          <div className="rounded-md border">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 sticky top-0 z-10 shadow-sm">
                  <tr className="border-b">
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      ID
                    </th>
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      Name
                    </th>
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      Email
                    </th>
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      Status
                    </th>
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      Created
                    </th>
                    <th className="h-10 px-4 font-medium text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Mail className="h-3 w-3" /> Portal Invite
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filtered.map((client) => (
                    <tr
                      key={client.id}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <td className="p-4 font-mono text-xs text-muted-foreground">
                        {client.id}
                      </td>
                      <td className="p-4 font-medium">
                        {client.full_name ?? "—"}
                      </td>
                      <td className="p-4 text-muted-foreground">
                        {client.email ?? "—"}
                      </td>
                      <td className="p-4">
                        {client.status ? (
                          <Badge variant="outline" className="text-xs">
                            {client.status}
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="p-4 text-xs text-muted-foreground whitespace-nowrap">
                        {client.created_at
                          ? new Date(client.created_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="p-4">
                        {client.email ? (
                          <InviteClientButton
                            clientId={client.id}
                            clientEmail={client.email}
                            clientName={client.full_name}
                          />
                        ) : (
                          <span className="text-xs text-muted-foreground italic">
                            No email
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
