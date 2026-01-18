'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Send, Camera, Twitter, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
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
  const [selectedTelegramChatId, setSelectedTelegramChatId] = useState<string | number | null>(null);
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
  const loadMessages = useCallback(async (channel: Channel, identifier: string | number) => {
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
          const telegramConv = telegramConversations.find((c) => String(c.chat_id) === String(identifier));
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
          const instagramConv = instagramConversations.find((c) => c.instagram_user_id === identifier);
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
  }, [whatsappConversations, telegramConversations, instagramConversations, twitterConversations]);

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
    async (channel: Channel, text: string, identifier: string | number, replyToMessageId?: string) => {
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

  const channels: Array<{ id: Channel; label: string; icon: React.ReactNode; activeClass: string }> = [
    { id: 'whatsapp', label: 'WhatsApp', icon: <MessageSquare className="w-4 h-4" />, activeClass: 'bg-green-500 text-white' },
    { id: 'telegram', label: 'Telegram', icon: <Send className="w-4 h-4" />, activeClass: 'bg-blue-500 text-white' },
    { id: 'instagram', label: 'Instagram', icon: <Camera className="w-4 h-4" />, activeClass: 'bg-gradient-to-r from-purple-500 to-pink-500 text-white' },
    { id: 'twitter', label: 'Twitter/X', icon: <Twitter className="w-4 h-4" />, activeClass: 'bg-black dark:bg-white text-white dark:text-black' },
  ];

  return (
    <div className="h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 flex flex-col">
      {/* Channel Tabs */}
      <div className="flex items-center gap-2 p-4 border-b border-[var(--border)] bg-[var(--background-secondary)]">
        {channels.map((channel) => (
          <button
            key={channel.id}
            onClick={() => handleChannelChange(channel.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
              activeChannel === channel.id
                ? channel.activeClass
                : 'bg-[var(--background)] text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)]'
            )}
          >
            {channel.icon}
            <span className="text-sm font-medium">{channel.label}</span>
            {channel.id === 'whatsapp' && whatsappConversations.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs">
                {whatsappConversations.length}
              </span>
            )}
            {channel.id === 'telegram' && telegramConversations.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs">
                {telegramConversations.length}
              </span>
            )}
            {channel.id === 'instagram' && instagramConversations.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs">
                {instagramConversations.length}
              </span>
            )}
            {channel.id === 'twitter' && twitterConversations.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs">
                {twitterConversations.length}
              </span>
            )}
          </button>
        ))}
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
