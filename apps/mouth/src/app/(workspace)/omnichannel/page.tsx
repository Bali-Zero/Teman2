'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { logger } from '@/lib/logger';
import { WhatsAppList, WhatsAppViewer } from '@/components/whatsapp';
import { TelegramList, TelegramViewer } from '@/components/telegram';
import { InstagramList, InstagramViewer } from '@/components/instagram';
import { TwitterList, TwitterViewer } from '@/components/twitter';
import type { WhatsAppConversation, WhatsAppMessage } from '@/lib/api/whatsapp/whatsapp.types';
import type { TelegramConversation, TelegramMessage } from '@/lib/api/telegram/telegram.types';
import type { InstagramConversation, InstagramMessage } from '@/lib/api/instagram/instagram.types';
import type { TwitterConversation, TwitterMessage } from '@/lib/api/twitter/twitter.types';
import type { Client } from '@/lib/api/crm/crm.types';

type Channel = 'whatsapp' | 'telegram' | 'instagram' | 'twitter';

export default function OmnichannelPage() {
  const [activeChannel, setActiveChannel] = useState<Channel>('whatsapp');

  // WhatsApp state
  const [whatsappConversations, setWhatsappConversations] = useState<WhatsAppConversation[]>([]);
  const [selectedWhatsappPhone, setSelectedWhatsappPhone] = useState<string | null>(null);
  const [whatsappMessages, setWhatsappMessages] = useState<WhatsAppMessage[]>([]);
  const [whatsappClient, setWhatsappClient] = useState<Client | null>(null);
  const [isLoadingWhatsapp, setIsLoadingWhatsapp] = useState(true);

  // Telegram state
  const [telegramConversations, setTelegramConversations] = useState<TelegramConversation[]>([]);
  const [selectedTelegramChatId, setSelectedTelegramChatId] = useState<string | number | null>(
    null
  );
  const [telegramMessages, setTelegramMessages] = useState<TelegramMessage[]>([]);
  const [telegramClient, setTelegramClient] = useState<Client | null>(null);
  const [isLoadingTelegram, setIsLoadingTelegram] = useState(true);

  // Instagram state
  const [instagramConversations, setInstagramConversations] = useState<InstagramConversation[]>([]);
  const [selectedInstagramUserId, setSelectedInstagramUserId] = useState<string | null>(null);
  const [instagramMessages, setInstagramMessages] = useState<InstagramMessage[]>([]);
  const [instagramClient, setInstagramClient] = useState<Client | null>(null);
  const [isLoadingInstagram, setIsLoadingInstagram] = useState(true);

  // Twitter state
  const [twitterConversations, setTwitterConversations] = useState<TwitterConversation[]>([]);
  const [selectedTwitterUserId, setSelectedTwitterUserId] = useState<string | null>(null);
  const [twitterMessages, setTwitterMessages] = useState<TwitterMessage[]>([]);
  const [twitterClient, setTwitterClient] = useState<Client | null>(null);
  const [isLoadingTwitter, setIsLoadingTwitter] = useState(true);

  // Force sync handler
  const handleForceSync = async () => {
    const toastId = toast.loading('Syncing omnichannel data...');
    try {
      setIsLoadingWhatsapp(true);
      setIsLoadingTelegram(true);
      setIsLoadingInstagram(true);
      setIsLoadingTwitter(true);

      // Parallel fetch with cache busting
      const [wa, tg, ig, tw] = await Promise.all([
        api.whatsapp.getConversations({ limit: 50 }),
        api.telegram.getConversations({ limit: 50 }),
        api.instagram.getConversations({ limit: 50 }),
        api.twitter.getConversations({ limit: 50 })
      ]);

      setWhatsappConversations(wa);
      setTelegramConversations(tg);
      setInstagramConversations(ig);
      setTwitterConversations(tw);

      toast.success('Sync complete', { id: toastId });
    } catch (error) {
      logger.error('Sync failed:', {}, error as Error);
      toast.error('Sync failed. Check logs.', { id: toastId });
    } finally {
      setIsLoadingWhatsapp(false);
      setIsLoadingTelegram(false);
      setIsLoadingInstagram(false);
      setIsLoadingTwitter(false);
    }
  };

  // Load conversations for active channel
  const loadConversations = useCallback(async (channel: Channel) => {
    try {
      switch (channel) {
        case 'whatsapp':
          setIsLoadingWhatsapp(true);
          const whatsappConvs = await api.whatsapp.getConversations({ limit: 50 });
          setWhatsappConversations(whatsappConvs);
          setIsLoadingWhatsapp(false);
          break;
        case 'telegram':
          setIsLoadingTelegram(true);
          const telegramConvs = await api.telegram.getConversations({ limit: 50 });
          setTelegramConversations(telegramConvs);
          setIsLoadingTelegram(false);
          break;
        case 'instagram':
          setIsLoadingInstagram(true);
          const instagramConvs = await api.instagram.getConversations({ limit: 50 });
          setInstagramConversations(instagramConvs);
          setIsLoadingInstagram(false);
          break;
        case 'twitter':
          setIsLoadingTwitter(true);
          const twitterConvs = await api.twitter.getConversations({ limit: 50 });
          setTwitterConversations(twitterConvs);
          setIsLoadingTwitter(false);
          break;
      }
    } catch (error) {
      logger.error(`Failed to load ${channel} conversations:`, {}, error as Error);
      switch (channel) {
        case 'whatsapp':
          setIsLoadingWhatsapp(false);
          break;
        case 'telegram':
          setIsLoadingTelegram(false);
          break;
        case 'instagram':
          setIsLoadingInstagram(false);
          break;
        case 'twitter':
          setIsLoadingTwitter(false);
          break;
      }
    }
  }, []);

  // Load messages for selected conversation
  const loadMessages = useCallback(
    async (channel: Channel, identifier: string | number) => {
      try {
        let client: Client | null = null;
        switch (channel) {
          case 'whatsapp':
            const whatsappMsgs = await api.whatsapp.getMessages(identifier as string, 100);
            setWhatsappMessages(whatsappMsgs);
            // Try to find client from conversations list
            const whatsappConv = whatsappConversations.find((c) => c.phone === identifier);
            if (whatsappConv?.client_id) {
              try {
                client = await api.crm.getClient(whatsappConv.client_id);
              } catch (e) {
                // Ignore errors
              }
            }
            setWhatsappClient(client);
            break;
          case 'telegram':
            const telegramMsgs = await api.telegram.getMessages(identifier, 100);
            setTelegramMessages(telegramMsgs);
            const telegramConv = telegramConversations.find(
              (c) => String(c.chat_id) === String(identifier)
            );
            if (telegramConv?.client_id) {
              try {
                client = await api.crm.getClient(telegramConv.client_id);
              } catch (e) {
                // Ignore errors
              }
            }
            setTelegramClient(client);
            break;
          case 'instagram':
            const instagramMsgs = await api.instagram.getMessages(identifier as string, 100);
            setInstagramMessages(instagramMsgs);
            const instagramConv = instagramConversations.find(
              (c) => c.instagram_user_id === identifier
            );
            if (instagramConv?.client_id) {
              try {
                client = await api.crm.getClient(instagramConv.client_id);
              } catch (e) {
                // Ignore errors
              }
            }
            setInstagramClient(client);
            break;
          case 'twitter':
            const twitterMsgs = await api.twitter.getMessages(identifier as string, 100);
            setTwitterMessages(twitterMsgs);
            const twitterConv = twitterConversations.find((c) => c.twitter_user_id === identifier);
            if (twitterConv?.client_id) {
              try {
                client = await api.crm.getClient(twitterConv.client_id);
              } catch (e) {
                // Ignore errors
              }
            }
            setTwitterClient(client);
            break;
        }
      } catch (error) {
        logger.error(`Failed to load ${channel} messages:`, {}, error as Error);
      }
    },
    [whatsappConversations, telegramConversations, instagramConversations, twitterConversations]
  );

  // Load conversations on mount and when channel changes
  useEffect(() => {
    loadConversations(activeChannel);
  }, [activeChannel, loadConversations]);

  // Load messages when a conversation is selected
  useEffect(() => {
    if (selectedWhatsappPhone) {
      loadMessages('whatsapp', selectedWhatsappPhone);
    }
  }, [selectedWhatsappPhone, loadMessages]);

  useEffect(() => {
    if (selectedTelegramChatId) {
      loadMessages('telegram', selectedTelegramChatId);
    }
  }, [selectedTelegramChatId, loadMessages]);

  useEffect(() => {
    if (selectedInstagramUserId) {
      loadMessages('instagram', selectedInstagramUserId);
    }
  }, [selectedInstagramUserId, loadMessages]);

  useEffect(() => {
    if (selectedTwitterUserId) {
      loadMessages('twitter', selectedTwitterUserId);
    }
  }, [selectedTwitterUserId, loadMessages]);

  // Handle channel switch
  const handleChannelChange = (channel: Channel) => {
    setActiveChannel(channel);
    // Clear selected conversations when switching channels
    setSelectedWhatsappPhone(null);
    setSelectedTelegramChatId(null);
    setSelectedInstagramUserId(null);
    setSelectedTwitterUserId(null);
  };

  // Handle send message
  const handleSendMessage = useCallback(
    async (
      channel: Channel,
      text: string,
      identifier: string | number,
      replyToMessageId?: string
    ) => {
      try {
        switch (channel) {
          case 'whatsapp':
            await api.whatsapp.sendMessage(identifier as string, text, replyToMessageId);
            await loadMessages('whatsapp', identifier as string);
            await loadConversations('whatsapp');
            break;
          case 'telegram':
            await api.telegram.sendMessage(identifier, text, replyToMessageId);
            await loadMessages('telegram', identifier);
            await loadConversations('telegram');
            break;
          case 'instagram':
            await api.instagram.sendMessage(identifier as string, text, replyToMessageId);
            await loadMessages('instagram', identifier as string);
            await loadConversations('instagram');
            break;
          case 'twitter':
            await api.twitter.sendMessage(identifier as string, text, replyToMessageId);
            await loadMessages('twitter', identifier as string);
            await loadConversations('twitter');
            break;
        }
      } catch (error) {
        logger.error(`Failed to send ${channel} message:`, {}, error as Error);
        throw error;
      }
    },
    [loadMessages, loadConversations]
  );

  // Channel configuration with brand colors and logos (fixed colors always visible)
  const channels: Array<{
    id: Channel;
    label: string;
    icon: React.ReactNode;
    baseClass: string; // Fixed color class for all states
    activeClass: string; // Additional class when active (shadow, etc)
  }> = [
    {
      id: 'whatsapp',
      label: 'WhatsApp',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
        </svg>
      ),
      baseClass: 'bg-[#25D366] text-white border-2 border-[#25D366]',
      activeClass: 'shadow-lg shadow-[#25D366]/30',
    },
    {
      id: 'telegram',
      label: 'Telegram',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.559z" />
        </svg>
      ),
      baseClass: 'bg-[#0088cc] text-white border-2 border-[#0088cc]',
      activeClass: 'shadow-lg shadow-[#0088cc]/30',
    },
    {
      id: 'instagram',
      label: 'Instagram',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
        </svg>
      ),
      baseClass:
        'bg-gradient-to-r from-[#E4405F] to-[#833AB4] text-white border-2 border-transparent',
      activeClass: 'shadow-lg shadow-[#E4405F]/30',
    },
    {
      id: 'twitter',
      label: 'X',
      icon: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      ),
      baseClass: 'bg-black text-white border-2 border-black',
      activeClass: 'shadow-lg shadow-black/30',
    },
  ];

  return (
    <div className="h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 flex flex-col">
      {/* Channel Tabs */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="flex items-center gap-3">
          {channels.map((channel) => {
            const conversationCount =
              channel.id === 'whatsapp'
              ? whatsappConversations.length
              : channel.id === 'telegram'
                ? telegramConversations.length
                : channel.id === 'instagram'
                  ? instagramConversations.length
                  : twitterConversations.length;

          const isActive = activeChannel === channel.id;

          return (
            <button
              key={channel.id}
              onClick={() => handleChannelChange(channel.id)}
              className={cn(
                'flex items-center gap-2.5 px-4 py-2.5 rounded-lg transition-all duration-200 font-medium',
                channel.baseClass, // Fixed brand color always visible
                isActive ? channel.activeClass : 'opacity-90 hover:opacity-100 hover:scale-105'
              )}
            >
              <span className="flex-shrink-0 text-white">{channel.icon}</span>
              <span className="text-sm font-semibold text-white">{channel.label}</span>
              {conversationCount > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-white/30 text-white">
                  {conversationCount}
                </span>
              )}
            </button>
                      );
                    })}
                  </div>
                  
                  <button
                    onClick={handleForceSync}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)] hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all text-xs font-medium text-[var(--foreground-muted)] hover:text-[var(--accent)]"
                    title="Force refresh data"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Sync
                  </button>
                </div>
                {/* Channel Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Conversations List */}
        <div className="w-96 border-r border-[var(--border)] bg-[var(--background)] flex flex-col">
          {activeChannel === 'whatsapp' && (
            <WhatsAppList
              conversations={whatsappConversations}
              selectedPhone={selectedWhatsappPhone}
              selectedIds={new Set()}
              onSelectConversation={setSelectedWhatsappPhone}
              onToggleSelect={() => {}}
              onSelectAll={() => {}}
              onSearch={() => {}}
              searchQuery=""
              isLoading={isLoadingWhatsapp}
            />
          )}
          {activeChannel === 'telegram' && (
            <TelegramList
              conversations={telegramConversations}
              selectedChatId={selectedTelegramChatId}
              selectedIds={new Set()}
              onSelectConversation={setSelectedTelegramChatId}
              onToggleSelect={() => {}}
              onSelectAll={() => {}}
              onSearch={() => {}}
              searchQuery=""
              isLoading={isLoadingTelegram}
            />
          )}
          {activeChannel === 'instagram' && (
            <InstagramList
              conversations={instagramConversations}
              selectedUserId={selectedInstagramUserId}
              selectedIds={new Set()}
              onSelectConversation={setSelectedInstagramUserId}
              onToggleSelect={() => {}}
              onSelectAll={() => {}}
              onSearch={() => {}}
              searchQuery=""
              isLoading={isLoadingInstagram}
            />
          )}
          {activeChannel === 'twitter' && (
            <TwitterList
              conversations={twitterConversations}
              selectedUserId={selectedTwitterUserId}
              selectedIds={new Set()}
              onSelectConversation={setSelectedTwitterUserId}
              onToggleSelect={() => {}}
              onSelectAll={() => {}}
              onSearch={() => {}}
              searchQuery=""
              isLoading={isLoadingTwitter}
            />
          )}
        </div>

        {/* Messages Viewer */}
        <div className="flex-1 flex flex-col">
          {activeChannel === 'whatsapp' && (
            <WhatsAppViewer
              phone={selectedWhatsappPhone}
              messages={whatsappMessages}
              client={whatsappClient}
              onClose={() => setSelectedWhatsappPhone(null)}
              onSendMessage={(text, replyTo) =>
                handleSendMessage('whatsapp', text, selectedWhatsappPhone!, replyTo)
              }
              isLoading={false}
            />
          )}
          {activeChannel === 'telegram' && (
            <TelegramViewer
              chatId={selectedTelegramChatId}
              messages={telegramMessages}
              client={telegramClient}
              onClose={() => setSelectedTelegramChatId(null)}
              onSendMessage={(text, replyTo) =>
                handleSendMessage('telegram', text, selectedTelegramChatId!, replyTo)
              }
              isLoading={false}
            />
          )}
          {activeChannel === 'instagram' && (
            <InstagramViewer
              instagramUserId={selectedInstagramUserId}
              messages={instagramMessages}
              client={instagramClient}
              onClose={() => setSelectedInstagramUserId(null)}
              onSendMessage={(text, replyTo) =>
                handleSendMessage('instagram', text, selectedInstagramUserId!, replyTo)
              }
              isLoading={false}
            />
          )}
          {activeChannel === 'twitter' && (
            <TwitterViewer
              twitterUserId={selectedTwitterUserId}
              messages={twitterMessages}
              client={twitterClient}
              onClose={() => setSelectedTwitterUserId(null)}
              onSendMessage={(text, replyTo) =>
                handleSendMessage('twitter', text, selectedTwitterUserId!, replyTo)
              }
              isLoading={false}
            />
          )}
        </div>
      </div>
    </div>
  );
}
