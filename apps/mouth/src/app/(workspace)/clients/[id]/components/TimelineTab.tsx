'use client';

import React from 'react';
import { Clock, MessageCircle } from 'lucide-react';
import type { Interaction } from '@/lib/api/crm/crm.types';
import { INTERACTION_ICONS } from './utils';

export function TimelineTab({
  interactions,
  formatDate,
  formatTime,
}: {
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Activity Timeline</h3>

      {interactions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <Clock className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No activity yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {interactions.map((interaction, idx) => (
            <div key={interaction.id} className="flex gap-3">
              {/* Timeline Line */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    interaction.interaction_type === 'whatsapp'
                      ? 'bg-green-500/20 text-green-500'
                      : interaction.interaction_type === 'email'
                        ? 'bg-blue-500/20 text-blue-500'
                        : interaction.interaction_type === 'call'
                          ? 'bg-purple-500/20 text-purple-500'
                          : 'bg-[var(--bz-accent)]/20 text-[var(--bz-accent)]'
                  }`}
                >
                  {INTERACTION_ICONS[interaction.interaction_type] || (
                    <MessageCircle className="w-4 h-4" />
                  )}
                </div>
                {idx < interactions.length - 1 && (
                  <div className="w-0.5 h-full min-h-[40px] bg-[var(--border)]" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-[var(--bz-text-1)]">
                      {interaction.interaction_type.charAt(0).toUpperCase() +
                        interaction.interaction_type.slice(1)}
                    </span>
                    <span className="text-[10px] text-[var(--bz-text-2)]">
                      {formatDate(interaction.interaction_date)}{' '}
                      {formatTime(interaction.interaction_date)}
                    </span>
                  </div>
                  {interaction.subject && (
                    <p className="text-sm text-[var(--bz-text-1)] mb-1">{interaction.subject}</p>
                  )}
                  {interaction.summary && (
                    <p className="text-xs text-[var(--bz-text-2)] line-clamp-2">
                      {interaction.summary}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-[10px] text-[var(--bz-text-2)]">
                    <span>{interaction.team_member}</span>
                    {interaction.sentiment && (
                      <span
                        className={`px-1.5 py-0.5 rounded ${
                          interaction.sentiment === 'positive'
                            ? 'bg-green-500/20 text-green-400'
                            : interaction.sentiment === 'negative'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {interaction.sentiment}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
