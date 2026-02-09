import React from 'react';
import { EnrichedConversation, ChannelType } from '../types';
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Filter, Phone, Send, Instagram } from "lucide-react";
import { cn } from "@/lib/utils";

interface InboxSidebarProps {
  conversations: EnrichedConversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  isLoading: boolean;
}

export function InboxSidebar({ conversations, selectedId, onSelect, isLoading }: InboxSidebarProps) {
  const [filter, setFilter] = React.useState('');

  const filtered = conversations.filter(c => 
    c.client_name?.toLowerCase().includes(filter.toLowerCase()) || 
    c.phone.includes(filter)
  );

  const ChannelIcon = ({ type }: { type: ChannelType }) => {
    switch (type) {
      case 'whatsapp': return <Phone className="w-3 h-3" />;
      case 'telegram': return <Send className="w-3 h-3" />;
      case 'instagram': return <Instagram className="w-3 h-3" />;
      default: return <Phone className="w-3 h-3" />;
    }
  };

  return (
    <div className="w-[350px] flex flex-col border-r border-border bg-card h-full">
      {/* Header & Search */}
      <div className="p-4 border-b border-border space-y-4">
        <h2 className="font-bold text-lg tracking-tight px-1">Inbox</h2>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search leads..." 
            className="pl-9 bg-background"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          <Badge variant="secondary" className="cursor-pointer hover:bg-secondary/80">All</Badge>
          <Badge variant="outline" className="cursor-pointer hover:bg-muted">Unread</Badge>
          <Badge variant="outline" className="cursor-pointer hover:bg-muted">My Leads</Badge>
          <Badge variant="outline" className="cursor-pointer hover:bg-muted">High Priority</Badge>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground text-sm">Loading conversations...</div>
        ) : (
          <div className="divide-y divide-border">
            {filtered.map((conv) => (
              <div 
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={cn(
                  "p-4 cursor-pointer hover:bg-accent/50 transition-colors group relative",
                  selectedId === conv.id && "bg-accent border-l-4 border-l-primary pl-[13px]"
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-semibold text-sm flex items-center gap-2">
                    {conv.client_name}
                    {conv.unread_count > 0 && (
                      <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {new Date(conv.last_message_date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </span>
                </div>
                
                <p className="text-xs text-muted-foreground line-clamp-2 mb-2 pr-4 leading-relaxed">
                  {conv.last_message || "No messages yet"}
                </p>

                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="outline" className={cn(
                    "text-[10px] px-1.5 h-5 gap-1 font-normal",
                    conv.channel === 'whatsapp' && "bg-green-50 text-green-700 border-green-200",
                    conv.channel === 'telegram' && "bg-blue-50 text-blue-700 border-blue-200",
                    conv.channel === 'instagram' && "bg-pink-50 text-pink-700 border-pink-200",
                  )}>
                    <ChannelIcon type={conv.channel} />
                    {conv.channel}
                  </Badge>
                  
                  {/* Mock Status Badge */}
                  <Badge variant="secondary" className="text-[10px] px-1.5 h-5 font-normal bg-gray-100 text-gray-600">
                    {conv.status || 'New'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
