'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { Plus, FolderOpen, Calendar, Edit2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { ClientProfile } from '@/lib/api/crm/crm.types';
import { STATUS_COLORS, ALERT_COLORS } from './constants';

export function ProcessTab({
  clientId,
  practices,
  formatDate,
  formatCurrency,
  router,
}: {
  clientId: number;
  practices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">All Process</h3>
        <Button
          size="sm"
          className="gap-2"
          onClick={() => router.push(`/process/new?client_id=${clientId}`)}
        >
          <Plus className="w-4 h-4" />
          New Process
        </Button>
      </div>

      {practices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <FolderOpen className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No process yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {practices.map((practice) => (
            <div
              key={practice.id}
              className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-4 hover:border-[var(--accent)]/50 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => router.push(`/process/${practice.id}`)}
                >
                  <span className="text-sm font-medium text-[var(--bz-text-1)]">
                    {practice.practice_type_name}
                  </span>
                  <span className="text-xs text-[var(--bz-text-2)] ml-2">#{practice.id}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {practice.status.replace(/_/g, ' ')}
                  </span>
                  {/* Edit/Delete buttons - show on hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/process/${practice.id}/edit`);
                      }}
                      className="p-1 rounded hover:bg-[var(--bz-card)] text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                      title="Edit process"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (
                          confirm(
                            `Delete process "${practice.practice_type_name}"?\n\nThis will mark the process as cancelled.`
                          )
                        ) {
                          try {
                            const user = await api.getProfile();
                            await api.crm.deletePractice(practice.id, user.email);
                            toast.success('Process deleted');
                            window.location.reload();
                          } catch (err) {
                            toast.error('Error', {
                              description: (err as Error).message,
                            });
                          }
                        }
                      }}
                      className="p-1 rounded hover:bg-red-500/20 text-[var(--bz-text-2)] hover:text-red-500"
                      title="Delete process"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              {practice.expiry_date && (
                <div
                  className={`text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded ${
                    ALERT_COLORS[practice.alert_color || 'green']
                  }`}
                >
                  <Calendar className="w-3 h-3" />
                  Expires: {formatDate(practice.expiry_date)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
