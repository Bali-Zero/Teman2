import React, { useMemo } from "react";
import { EnrichedConversation, ChannelType } from "../types";
import { Input } from "@/components/ui/input";
import { Search, Phone, Send, Instagram } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

interface InboxSidebarProps {
  conversations: EnrichedConversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  isLoading: boolean;
  filterMode: "all" | "unread";
  onFilterChange: (mode: "all" | "unread") => void;
  systemStatus?: string;
}

export function InboxSidebar({
  conversations,
  selectedId,
  onSelect,
  isLoading,
  filterMode,
  onFilterChange,
  systemStatus,
}: InboxSidebarProps) {
  const [search, setSearch] = React.useState("");

  const isDegraded = systemStatus === "degraded";

  const selectedConv = useMemo(
    () => conversations.find((c) => c.id === selectedId),
    [conversations, selectedId],
  );
  const activeChannel = selectedConv?.channel;

  const filtered = useMemo(
    () =>
      conversations.filter((c) => {
        const nameMatch =
          c.client_name?.toLowerCase().includes(search.toLowerCase()) || false;
        const phoneMatch = c.phone?.includes(search) || false;
        return nameMatch || phoneMatch;
      }),
    [conversations, search],
  );

  const getChannelColor = (type?: ChannelType) => {
    switch (type) {
      case "whatsapp":
        return "bg-[#4ADE80]";
      case "telegram":
        return "bg-[#0088cc]";
      case "instagram":
        return "bg-[#C13584]";
      default:
        return "bg-slate-900";
    }
  };

  return (
    <div
      className={cn(
        "w-[350px] flex flex-col border-r border-white/20 h-full transition-colors duration-700 ease-in-out shadow-2xl z-20",
        getChannelColor(activeChannel),
      )}
    >
      {/* Header & Search */}
      <div className="p-4 border-b border-white/20 space-y-4 shadow-md bg-black/10">
        <h2 className="font-black text-xl tracking-tighter px-1 text-white uppercase italic drop-shadow-md text-center">
          INBOX v2.1
        </h2>

        {isDegraded && (
          <div className="bg-red-500/80 p-2 rounded text-[10px] font-black text-white uppercase tracking-widest animate-pulse border border-white/30 text-center">
            ⚠️ Database Offline - Mock Data Active
          </div>
        )}

        <div className="relative group">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-white group-focus-within:text-white transition-colors" />
          <Input
            placeholder="Search leads..."
            className="pl-9 bg-black/30 border-white/40 text-white placeholder:text-white/70 focus-visible:ring-white font-black transition-all shadow-inner"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <div
            onClick={() => onFilterChange("all")}
            className={cn(
              "flex-1 text-center py-1 rounded-full text-[10px] font-black cursor-pointer shadow-lg transition-all uppercase tracking-widest",
              filterMode === "all"
                ? "bg-white text-black scale-105"
                : "bg-black/20 text-white/60 border border-white/10",
            )}
          >
            ALL
          </div>
          <div
            onClick={() => onFilterChange("unread")}
            className={cn(
              "flex-1 text-center py-1 rounded-full text-[10px] font-black cursor-pointer shadow-lg transition-all uppercase tracking-widest",
              filterMode === "unread"
                ? "bg-white text-black scale-105"
                : "bg-black/20 text-white/60 border border-white/10",
            )}
          >
            UNREAD
          </div>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <AnimatePresence>
          {isLoading ? (
            <div className="p-4 space-y-4">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="flex flex-col gap-2">
                  <div className="flex justify-between">
                    <Skeleton className="h-4 w-24 bg-white/30" />
                    <Skeleton className="h-3 w-12 bg-white/20" />
                  </div>
                  <Skeleton className="h-3 w-full bg-white/20" />
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y divide-white/10">
              {filtered.length > 0 ? (
                filtered.map((conv) => (
                  <motion.div
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    key={conv.id}
                    onClick={() => onSelect(conv.id)}
                    className={cn(
                      "p-4 cursor-pointer transition-all group relative border-l-[8px] border-l-transparent",
                      selectedId === conv.id
                        ? "bg-black/30 border-l-white shadow-2xl z-10"
                        : "hover:bg-black/10",
                    )}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <div className="font-black text-sm flex items-center gap-2 text-white tracking-tight drop-shadow-sm">
                        {conv.client_name || conv.phone}
                        {conv.unreadCount > 0 && (
                          <span className="w-3 h-3 bg-white rounded-full shadow-[0_0_15px_rgba(255,255,255,1)] animate-pulse" />
                        )}
                      </div>
                      <span className="text-[10px] text-white font-black uppercase opacity-70">
                        {new Date(conv.last_message_date).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" },
                        )}
                      </span>
                    </div>

                    <p className="text-xs text-white line-clamp-2 mb-2 pr-4 leading-relaxed font-black tracking-tight drop-shadow-sm">
                      {conv.last_message || "No messages yet"}
                    </p>

                    <div className="flex items-center gap-2 mt-2">
                      <div className="text-[9px] px-2 py-0.5 flex items-center gap-1 rounded bg-white text-black font-black uppercase shadow-lg">
                        <Phone className="w-3 h-3" />
                        <span>{conv.channel}</span>
                      </div>

                      <div
                        className={cn(
                          "text-[9px] px-2 py-0.5 flex items-center rounded bg-black/50 text-white border border-white/20 font-black uppercase tracking-widest shadow-sm",
                          conv.status === "closed" && "opacity-50",
                        )}
                      >
                        {conv.status || "New"}
                      </div>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="p-10 text-center space-y-4">
                  <div className="text-white/30 text-xs font-black uppercase tracking-widest">
                    No leads found in inbox
                  </div>
                  {isDegraded && (
                    <div className="text-[10px] text-red-300/60 font-medium italic">
                      Check database connection or try refreshing
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
