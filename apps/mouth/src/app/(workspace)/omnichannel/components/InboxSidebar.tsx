import React, { useMemo } from 'react';
import { EnrichedConversation, ChannelType } from '../types';
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
}

export function InboxSidebar({ conversations, selectedId, onSelect, isLoading }: InboxSidebarProps) {
  const [filter, setFilter] = React.useState('');

  const selectedConv = useMemo(() => conversations.find(c => c.id === selectedId), [conversations, selectedId]);
  const activeChannel = selectedConv?.channel;

  const filtered = useMemo(() => 
    conversations.filter(c => 
      (c.client_name?.toLowerCase().includes(filter.toLowerCase()) || 
       c.phone.includes(filter))
    ), [conversations, filter]
  );

  const getChannelColor = (type?: ChannelType) => {
    switch (type) {
      case 'whatsapp': return 'bg-[#25D366]';
      case 'telegram': return 'bg-[#0088cc]';
      case 'instagram': return 'bg-[#C13584]';
      default: return 'bg-slate-900';
    }
  };

  const ChannelIcon = ({ type }: { type: ChannelType }) => {
    switch (type) {
      case 'whatsapp': return <Phone className="w-3 h-3 text-white" />;
      case 'telegram': return <Send className="w-3 h-3 text-white" />;
      case 'instagram': return <Instagram className="w-3 h-3 text-white" />;
      default: return <Phone className="w-3 h-3 text-white" />;
    }
  };

  return (
    <div className={cn(
      "w-[350px] flex flex-col border-r border-white/10 h-full transition-colors duration-700 ease-in-out shadow-2xl z-20",
      getChannelColor(activeChannel)
    )}>
      {/* Header & Search */}
      <div className="p-4 border-b border-white/10 space-y-4 shadow-md bg-black/5">
        <h2 className="font-black text-xl tracking-tighter px-1 text-white uppercase italic drop-shadow-md">Inbox</h2>
        <div className="relative group">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-white/60 group-focus-within:text-white transition-colors" />
          <Input 
            placeholder="Search leads..." 
            className="pl-9 bg-black/20 border-white/20 text-white placeholder:text-white/40 focus-visible:ring-white/50 font-bold transition-all"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <div className="px-4 py-1 rounded-full bg-white text-black text-[10px] font-black cursor-pointer shadow-lg hover:scale-105 active:scale-95 transition-all uppercase tracking-widest">ALL</div>
          <div className="px-4 py-1 rounded-full bg-black/20 text-white text-[10px] font-black cursor-pointer border border-white/20 hover:bg-black/30 transition-all uppercase tracking-widest">UNREAD</div>
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
                    <Skeleton className="h-4 w-24 bg-white/20" />
                    <Skeleton className="h-3 w-12 bg-white/10" />
                  </div>
                  <Skeleton className="h-3 w-full bg-white/10" />
                  <Skeleton className="h-3 w-2/3 bg-white/5" />
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y divide-white/10">
              {filtered.map((conv) => (
                <motion.div 
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  key={conv.id}
                  onClick={() => onSelect(conv.id)}
                  className={cn(
                    "p-4 cursor-pointer transition-all group relative border-l-[6px] border-l-transparent",
                    selectedId === conv.id 
                      ? "bg-black/25 border-l-white shadow-2xl z-10" 
                      : "hover:bg-black/15"
                  )}
                >
                  <div className="flex justify-between items-start mb-1">
                    <div className="font-black text-sm flex items-center gap-2 text-white tracking-tight drop-shadow-sm">
                      {conv.client_name || conv.phone}
                      {(conv.unreadCount || 0) > 0 && (
                        <span className="w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white shadow-[0_0_10px_rgba(239,68,68,0.8)] animate-pulse" />
                      )}
                    </div>
                    <span className="text-[10px] text-white/50 font-black uppercase">
                      {new Date(conv.last_message_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </span>
                  </div>
                  
                  <p className="text-xs text-white/80 line-clamp-2 mb-2 pr-4 leading-relaxed font-bold tracking-tight">
                    {conv.last_message || "No messages yet"}
                  </p>

                  <div className="flex items-center gap-2 mt-2">
                    <div className="text-[9px] px-2 py-0.5 flex items-center gap-1 rounded bg-white text-black font-black uppercase shadow-md">
                      <ChannelIcon type={conv.channel} />
                      <span className={cn(
                        conv.channel === 'whatsapp' && "text-green-600",
                        conv.channel === 'telegram' && "text-blue-600",
                        conv.channel === 'instagram' && "text-pink-600",
                      )}>{conv.channel}</span>
                    </div>
                    
                    <div className={cn(
                      "text-[9px] px-2 py-0.5 flex items-center rounded bg-black/40 text-white border border-white/10 font-black uppercase tracking-widest shadow-sm",
                      conv.status === 'closed' && "opacity-50"
                    )}>
                      {conv.status || 'New'}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
