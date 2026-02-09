import React from 'react';
import { EnrichedConversation, ChannelType } from '../types';
import { Input } from "@/components/ui/input";
import { Search, Phone, Send, Instagram } from "lucide-react";
import { cn } from "@/lib/utils";

interface InboxSidebarProps {
  conversations: EnrichedConversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  isLoading: boolean;
}

export function InboxSidebar({ conversations, selectedId, onSelect, isLoading }: InboxSidebarProps) {
  const [filter, setFilter] = React.useState('');

  const selectedConv = conversations.find(c => c.id === selectedId);
  const activeChannel = selectedConv?.channel;

  const filtered = conversations.filter(c => 
    (c.client_name?.toLowerCase().includes(filter.toLowerCase()) || 
     c.phone.includes(filter))
  );

  const getChannelColor = (type?: ChannelType) => {
    switch (type) {
      case 'whatsapp': return 'bg-[#25D366]'; // Vibrant WhatsApp Green
      case 'telegram': return 'bg-[#0088cc]'; // TG Blue
      case 'instagram': return 'bg-[#C13584]'; // IG Pink/Purple
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
      "w-[350px] flex flex-col border-r border-white/10 h-full transition-colors duration-500",
      getChannelColor(activeChannel)
    )}>
      {/* Header & Search */}
      <div className="p-4 border-b border-white/10 space-y-4">
        <h2 className="font-black text-xl tracking-tighter px-1 text-white uppercase italic">Inbox</h2>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-white/80" />
          <Input 
            placeholder="Search leads..." 
            className="pl-9 bg-black/20 border-white/30 text-white placeholder:text-white/60 focus-visible:ring-white/50 font-bold"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <div className="px-4 py-1 rounded-full bg-white text-black text-[10px] font-black cursor-pointer shadow-lg hover:scale-105 transition-transform">ALL</div>
          <div className="px-4 py-1 rounded-full bg-black/20 text-white text-[10px] font-black cursor-pointer border border-white/20 hover:bg-black/30 transition-all">UNREAD</div>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-white/60 text-xs font-black animate-pulse uppercase">Syncing Cloud Data...</div>
        ) : (
          <div className="divide-y divide-white/10">
            {filtered.map((conv) => (
              <div 
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={cn(
                  "p-4 cursor-pointer transition-all group relative border-l-[6px] border-l-transparent",
                  selectedId === conv.id 
                    ? "bg-black/20 border-l-white shadow-2xl scale-[1.02] z-10" 
                    : "hover:bg-black/10"
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-black text-sm flex items-center gap-2 text-white tracking-tight">
                    {conv.client_name || conv.phone}
                    {(conv.unreadCount || 0) > 0 && (
                      <span className="w-3 h-3 bg-red-500 rounded-full border-2 border-white shadow-lg animate-bounce" />
                    )}
                  </div>
                  <span className="text-[10px] text-white/60 font-black">
                    {new Date(conv.last_message_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </span>
                </div>
                
                <p className="text-xs text-white/90 line-clamp-2 mb-2 pr-4 leading-relaxed font-bold tracking-tight">
                  {conv.last_message || "No messages yet"}
                </p>

                <div className="flex items-center gap-2 mt-2">
                  <div className="text-[9px] px-2 py-0.5 flex items-center gap-1 rounded bg-white text-black font-black uppercase shadow-sm">
                    <ChannelIcon type={conv.channel} />
                    <span className={cn(
                      conv.channel === 'whatsapp' && "text-green-600",
                      conv.channel === 'telegram' && "text-blue-600",
                      conv.channel === 'instagram' && "text-pink-600",
                    )}>{conv.channel}</span>
                  </div>
                  
                  <div className="text-[9px] px-2 py-0.5 flex items-center rounded bg-black/40 text-white border border-white/10 font-black uppercase tracking-widest">
                    {conv.status || 'New'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}