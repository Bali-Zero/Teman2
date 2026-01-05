
import React from 'react';
import { motion } from 'framer-motion';
import { 
  MessageCircle, 
  Clock, 
  MoreHorizontal, 
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Mail,
  Phone
} from 'lucide-react';
import { Client } from '@/lib/api/crm/crm.types';
import { useRouter } from 'next/navigation';

interface ClientCardProps {
  client: Client;
  isDragging?: boolean;
}

const SENTIMENT_COLORS = {
  positive: 'ring-green-500',
  neutral: 'ring-yellow-500',
  negative: 'ring-red-500',
  mixed: 'ring-purple-500',
  none: 'ring-gray-200 dark:ring-gray-700'
};

const SENTIMENT_BG = {
  positive: 'bg-green-500/10 text-green-600 dark:text-green-400',
  neutral: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  negative: 'bg-red-500/10 text-red-600 dark:text-red-400',
  mixed: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  none: 'bg-gray-100 dark:bg-gray-800 text-gray-500'
};

// Helper to get default avatar based on client status
const getDefaultAvatar = (status: string): string => {
  const statusLower = status.toLowerCase();
  if (statusLower === 'lead') return '/avatars/default-lead.svg';
  if (statusLower === 'active') return '/avatars/default-active.svg';
  // Fallback: show first letter in colored circle (handled in render)
  return '';
};

export const ClientCard = ({ client, isDragging }: ClientCardProps) => {
  const router = useRouter();

  // Determine sentiment aura
  const sentiment = (client.last_sentiment || 'none').toLowerCase() as keyof typeof SENTIMENT_COLORS;
  const ringColor = SENTIMENT_COLORS[sentiment] || SENTIMENT_COLORS.none;
  const badgeStyle = SENTIMENT_BG[sentiment] || SENTIMENT_BG.none;

  // Get avatar URL: use client's avatar or fallback to default
  const avatarUrl = client.avatar_url || getDefaultAvatar(client.status);

  return (
    <div className="relative group perspective-1000">
      <motion.div
        layoutId={`client-${client.id}`}
        className={`
          relative bg-[var(--background-secondary)] rounded-xl border border-[var(--border)] 
          p-4 cursor-pointer hover:shadow-lg transition-all duration-300
          ${isDragging ? 'opacity-50 scale-95 rotate-3' : 'hover:-translate-y-1'}
        `}
        onClick={() => router.push(`/clients/${client.id}`)}
      >
        {/* Header with Avatar & Name */}
        <div className="flex items-start gap-3 mb-3">
          <div className={`relative w-10 h-10 rounded-full ${ringColor} ring-2 ring-offset-2 ring-offset-[var(--background-secondary)]`}>
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={client.full_name}
                className="w-full h-full rounded-full object-cover"
              />
            ) : (
              <div className="w-full h-full rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] font-bold">
                {client.full_name.charAt(0)}
              </div>
            )}

            {/* Status Dot */}
            <div className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-[var(--background-secondary)]
              ${client.status === 'active' ? 'bg-green-500' :
                client.status === 'lead' ? 'bg-blue-500' : 'bg-gray-400'}`}
            />
          </div>

          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-[var(--foreground)] truncate">{client.full_name}</h4>
            <div className="flex items-center gap-2 text-xs text-[var(--foreground-muted)]">
              <span className="truncate">{client.nationality || 'Unknown'}</span>
              {client.company_name && (
                <>
                  <span>•</span>
                  <span className="truncate max-w-[80px]">{client.company_name}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Strategic Peek Info (Always visible in card, but stylized) */}
        <div className="space-y-2 text-xs">
          {/* Last Interaction Summary */}
          {client.last_interaction_summary ? (
            <div className={`p-2 rounded-lg ${badgeStyle} line-clamp-2`}>
              <div className="flex items-center gap-1.5 mb-1 opacity-75">
                <MessageCircle className="w-3 h-3" />
                <span className="font-medium capitalize">{sentiment} Interaction</span>
              </div>
              "{client.last_interaction_summary}"
            </div>
          ) : (
            <div className="p-2 rounded-lg bg-[var(--background)] text-[var(--foreground-muted)] italic">
              No recent interactions
            </div>
          )}

          {/* Quick Stats Row */}
          <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[var(--foreground-muted)]">
            <div className="flex items-center gap-1.5" title="Last Contact">
              <Clock className="w-3 h-3" />
              <span>
                {client.last_interaction_date 
                  ? new Date(client.last_interaction_date).toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) 
                  : 'Never'}
              </span>
            </div>
            
            {/* Action Buttons (Visible on Hover) */}
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button className="p-1 hover:text-[var(--accent)] transition-colors">
                <Mail className="w-3 h-3" />
              </button>
              <button className="p-1 hover:text-green-500 transition-colors">
                <Phone className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </motion.div>

      {/* "Strategic Peek" Hover Effect - A floating detail card that appears on hover */}
      <div className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 translate-y-2 group-hover:translate-y-0">
        <div className="bg-black/90 backdrop-blur-md text-white p-3 rounded-lg shadow-xl text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="font-bold text-[var(--accent)]">WAR ROOM INTEL</span>
            <TrendingUp className="w-3 h-3 text-green-400" />
          </div>
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <span className="text-gray-400">Value:</span>
              <span className="font-mono text-green-400">$High</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Next Step:</span>
              <span>Follow-up (3d)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Sentiment:</span>
              <span className="capitalize text-white">{sentiment}</span>
            </div>
          </div>
          <div className="absolute bottom-[-4px] left-1/2 -translate-x-1/2 w-2 h-2 bg-black/90 rotate-45"></div>
        </div>
      </div>
    </div>
  );
};
