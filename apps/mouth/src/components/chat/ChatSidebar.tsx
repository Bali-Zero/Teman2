'use client';

import Image from 'next/image';
import { useRouter } from 'next/navigation';
import {
  X,
  Plus,
  MessageSquare,
  Settings,
  HelpCircle,
  Home,
  Trash2,
  Search,
  Loader2,
} from 'lucide-react';

export interface Conversation {
  id: number;
  title: string | null;
  created_at: string;
  updated_at?: string;
  message_count?: number;
}

export interface ChatSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onConversationClick: (id: number) => void;
  onDeleteConversation: (id: number, e: React.MouseEvent) => void;
  onSearchDocsOpen: () => void;
  conversations: Conversation[];
  currentConversationId: number | null;
  isLoading: boolean;
}

/**
 * Chat sidebar with conversation history
 */
export function ChatSidebar({
  isOpen,
  onClose,
  onNewChat,
  onConversationClick,
  onDeleteConversation,
  onSearchDocsOpen,
  conversations,
  currentConversationId,
  isLoading,
}: ChatSidebarProps) {
  const router = useRouter();

  return (
    <>
      {/* Sidebar Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full w-72 bg-[#1a1a1a] border-r border-white/5 z-50 transform transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Sidebar Header */}
          <div className="h-14 border-b border-white/5 flex items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <Image
                src="/assets/logo_zan.png"
                alt="Zantara"
                width={32}
                height={32}
                className="drop-shadow-[0_0_12px_rgba(255,255,255,0.3)]"
              />
              <span className="font-medium text-white/90">Zantara</span>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-4">
            <button
              onClick={onNewChat}
              className="w-full flex items-center gap-3 px-4 py-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors text-gray-300"
            >
              <Plus className="w-5 h-5" />
              <span>New Chat</span>
            </button>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto px-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Recent Chats</p>
            {isLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No conversations yet</p>
            ) : (
              <div className="space-y-1">
                {conversations.slice(0, 10).map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => onConversationClick(conv.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors text-left group ${
                      currentConversationId === conv.id ? 'bg-white/10' : ''
                    }`}
                  >
                    <MessageSquare className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="text-sm text-gray-400 truncate flex-1">
                      {conv.title || 'Untitled'}
                    </span>
                    <button
                      onClick={(e) => onDeleteConversation(conv.id, e)}
                      className="p-1 hover:bg-white/10 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-gray-500 hover:text-red-400" />
                    </button>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar Footer */}
          <div className="border-t border-white/5 p-4 space-y-1">
            <button
              onClick={onSearchDocsOpen}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors"
            >
              <Search className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Search Docs</span>
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors">
              <Settings className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Settings</span>
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors">
              <HelpCircle className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Help</span>
            </button>
            <button
              onClick={() => router.push('/dashboard')}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors text-blue-400"
            >
              <Home className="w-4 h-4" />
              <span className="text-sm">Dashboard</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
