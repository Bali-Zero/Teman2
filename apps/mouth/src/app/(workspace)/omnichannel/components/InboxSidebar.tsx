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
      case 'whatsapp': return 'bg-[#075E54]'; // WA Dark Green
      case 'telegram': return 'bg-[#0088cc]'; // TG Blue
      case 'instagram': return 'bg-[#C13584]'; // IG Pink/Purple
      default: return 'bg-slate-900';
    }
  };

  const ChannelIcon = ({ type }: { type: ChannelType }) => {
    switch (type) {
      case 'whatsapp': return <Phone className="w-3 h-3" />;
      case 'telegram': return <Send className="w-3 h-3" />;
      case 'instagram': return <Instagram className="w-3 h-3" />;
      default: return <Phone className="w-3 h-3" />;
    }
  };

  return (
    <div className={cn(
      "w-[350px] flex flex-col border-r border-white/10 h-full transition-colors duration-500",
      getChannelColor(activeChannel)
    )}>
      {/* Header & Search */}
      <div className="p-4 border-b border-white/10 space-y-4">
        <h2 className="font-bold text-lg tracking-tight px-1 text-white">Inbox</h2>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-white/60" />
          <Input 
            placeholder="Search leads..." 
            className="pl-9 bg-white/10 border-white/20 text-white placeholder:text-white/40 focus-visible:ring-white/30"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          <div className="px-3 py-1 rounded-full bg-white/20 text-white text-[10px] font-bold cursor-pointer hover:bg-white/30 transition-colors">ALL</div>
          <div className="px-3 py-1 rounded-full border border-white/20 text-white/80 text-[10px] font-bold cursor-pointer hover:bg-white/10 transition-colors">UNREAD</div>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-white/40 text-sm">Loading conversations...</div>
        ) : (
          <div className="divide-y divide-white/5">
            {filtered.map((conv) => (
              <div 
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={cn(
                  "p-4 cursor-pointer transition-all group relative border-l-4 border-l-transparent",
                  selectedId === conv.id 
                    ? "bg-white/10 border-l-white shadow-inner" 
                    : "hover:bg-white/5"
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-bold text-sm flex items-center gap-2 text-white">
                    {conv.client_name || conv.phone}
                    {(conv.unreadCount || 0) > 0 && (
                      <span className="w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_8px_rgba(250,204,21,0.6)]" />
                    )}
                  </div>
                  <span className="text-[10px] text-white/50 font-medium">
                    {new Date(conv.last_message_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </span>
                </div>
                
                <p className="text-xs text-white/70 line-clamp-2 mb-2 pr-4 leading-relaxed font-medium">
                  {conv.last_message || "No messages yet"}
                </p>

                <div className="flex items-center gap-2 mt-2">
                  <div className="text-[9px] px-2 py-0.5 flex items-center gap-1 rounded-full bg-white/10 text-white border border-white/10 font-bold uppercase tracking-tighter">
                    <ChannelIcon type={conv.channel} />
                    {conv.channel}
                  </div>
                  
                  <div className="text-[9px] px-2 py-0.5 flex items-center rounded-full bg-black/20 text-white/80 border border-white/5 font-bold uppercase tracking-tighter">
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
