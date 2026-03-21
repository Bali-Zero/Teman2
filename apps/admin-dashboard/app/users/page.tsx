"use client";
import { useState, useEffect } from "react";
import { error as logError } from "@/lib/logger";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/primitives";
import { UserCog, Search, Brain, Fingerprint } from "lucide-react";
import { cn } from "@/lib/utils";

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [details, setDetails] = useState<{
    facts: any[];
    memories: any[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async (q = "") => {
    setLoading(true);
    try {
      const res = await fetch(`/api/postgres/users${q ? `?search=${q}` : ""}`);
      const data = await res.json();
      if (data.users) setUsers(data.users);
    } catch (e) {
      logError(e as string);
    } finally {
      setLoading(false);
    }
  };

  const selectUser = async (user: any) => {
    setSelectedUser(user);
    setDetailsLoading(true);
    try {
      const res = await fetch(`/api/postgres/users?userId=${user.id}`);
      const data = await res.json();
      setDetails({ facts: data.facts || [], memories: data.memories || [] });
    } catch (e) {
      logError(e as string);
    } finally {
      setDetailsLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* LEFT: User List */}
      <div className="w-1/3 border-r bg-muted/10 flex flex-col">
        <div className="p-4 border-b space-y-4">
          <div className="flex items-center gap-2">
            <UserCog className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold tracking-tight">User Context</h1>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              className="w-full bg-background border rounded-md pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchUsers(search)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2 space-y-2">
          {loading ? (
            <div className="p-4 text-center text-muted-foreground">
              Loading...
            </div>
          ) : (
            users.map((user) => (
              <div
                key={user.id}
                onClick={() => selectUser(user)}
                className={cn(
                  "p-3 rounded-md border cursor-pointer hover:bg-muted transition-all",
                  selectedUser?.id === user.id
                    ? "bg-primary/5 border-primary shadow-sm"
                    : "bg-card border-transparent",
                )}
              >
                <div className="font-semibold">
                  {user.full_name || "Unnamed User"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {user.email}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                  {user.id}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* RIGHT: Context Details */}
      <div className="flex-1 overflow-auto bg-background p-8">
        {!selectedUser ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
            <UserCog className="h-16 w-16 mb-4 opacity-20" />
            <p>Select a user to inspect their long-term memory and facts.</p>
          </div>
        ) : (
          <div className="space-y-8 max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-3xl font-bold">{selectedUser.full_name}</h2>
                <div className="text-muted-foreground">
                  {selectedUser.email}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-muted-foreground">User ID</div>
                <code className="bg-muted px-2 py-1 rounded text-xs">
                  {selectedUser.id}
                </code>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Facts */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Fingerprint className="h-5 w-5" />
                    Extracted Facts
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {detailsLoading ? (
                    <div className="text-sm text-muted-foreground">
                      Loading context...
                    </div>
                  ) : details?.facts.length === 0 ? (
                    <div className="text-sm text-muted-foreground italic">
                      No facts extracted yet.
                    </div>
                  ) : (
                    details?.facts.map((fact, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-start border-b pb-2 last:border-0"
                      >
                        <span className="font-medium text-sm">{fact.key}</span>
                        <span className="text-sm text-muted-foreground text-right">
                          {fact.value}
                        </span>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              {/* Memories */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    Episodic Memory
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {detailsLoading ? (
                    <div className="text-sm text-muted-foreground">
                      Loading memories...
                    </div>
                  ) : details?.memories.length === 0 ? (
                    <div className="text-sm text-muted-foreground italic">
                      No memories recorded yet.
                    </div>
                  ) : (
                    details?.memories.map((mem, i) => (
                      <div
                        key={i}
                        className="bg-muted/30 p-3 rounded-md text-sm"
                      >
                        <p className="mb-1">{mem.content}</p>
                        <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-2">
                          <span>
                            {new Date(mem.created_at).toLocaleDateString()}
                          </span>
                          <Badge variant="outline" className="text-[10px] h-5">
                            {mem.type || "general"}
                          </Badge>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
