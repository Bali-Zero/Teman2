'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { CRMContext, Thread } from '@/lib/api/omnichannel/omnichannel.types';

interface CRMPanelProps {
  thread: Thread | null;
  context: CRMContext | null;
  isLoading: boolean;
  onAssign: (email: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  inquiry: 'bg-blue-500/20 text-blue-400',
  waiting_documents: 'bg-yellow-500/20 text-yellow-400',
  sending_invoice: 'bg-purple-500/20 text-purple-400',
  on_process: 'bg-orange-500/20 text-orange-400',
  completed: 'bg-green-500/20 text-green-400',
  cancelled: 'bg-red-500/20 text-red-400',
};

export function CRMPanel({ thread, context, isLoading, onAssign }: CRMPanelProps) {
  if (!thread) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--foreground-muted)] text-sm">
        Select a thread to view details
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--foreground-muted)] text-sm">
        Loading context...
      </div>
    );
  }

  const client = context?.client;

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-5">
        {/* Client Card */}
        <section>
          <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider mb-2">
            Client
          </h4>
          {client ? (
            <div className="rounded-lg bg-[var(--background-secondary)] p-3 space-y-2">
              <div className="flex items-center gap-2">
                {client.avatar_url ? (
                  <img
                    src={client.avatar_url}
                    alt=""
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center text-xs font-bold text-[var(--accent)]">
                    {(client.full_name || '?')[0].toUpperCase()}
                  </div>
                )}
                <div>
                  <p className="font-medium text-sm text-[var(--foreground)]">{client.full_name}</p>
                  <p className="text-xs text-[var(--foreground-muted)]">{client.email}</p>
                </div>
              </div>
              {client.phone && (
                <p className="text-xs text-[var(--foreground-muted)]">Phone: {client.phone}</p>
              )}
              {client.nationality && (
                <p className="text-xs text-[var(--foreground-muted)]">
                  Nationality: {client.nationality}
                </p>
              )}
              {client.company_name && (
                <p className="text-xs text-[var(--foreground-muted)]">
                  Company: {client.company_name}
                </p>
              )}
              <Badge variant="outline" className="text-[10px]">
                {client.status}
              </Badge>
            </div>
          ) : (
            <p className="text-xs text-[var(--foreground-muted)] italic">Unidentified sender</p>
          )}
        </section>

        {/* Assignment */}
        <section>
          <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider mb-2">
            Assignment
          </h4>
          <div className="space-y-2">
            <p className="text-sm text-[var(--foreground)]">{thread.assigned_to || 'Unassigned'}</p>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7"
                onClick={() => onAssign('zero@balizero.com')}
              >
                Assign to Zero
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7"
                onClick={() => onAssign('asya@balizero.com')}
              >
                Assign to Asya
              </Button>
            </div>
          </div>
        </section>

        {/* Active Practices */}
        {context?.practices && context.practices.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider mb-2">
              Practices ({context.practices.length})
            </h4>
            <div className="space-y-2">
              {context.practices.map((p) => (
                <div key={p.id} className="rounded bg-[var(--background-secondary)] p-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-[var(--foreground)]">
                      {p.practice_type}
                    </span>
                    <Badge
                      className={`text-[10px] ${STATUS_COLORS[p.status] || 'bg-gray-500/20 text-gray-400'}`}
                    >
                      {p.status}
                    </Badge>
                  </div>
                  {p.quoted_price && (
                    <p className="text-[10px] text-[var(--foreground-muted)] mt-1">
                      Rp {p.quoted_price.toLocaleString()}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Alerts */}
        {context?.alerts && context.alerts.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider mb-2">
              Alerts
            </h4>
            <div className="space-y-1">
              {context.alerts.map((a) => (
                <div key={a.id} className="text-xs p-2 rounded bg-red-500/10 text-red-400">
                  {a.message}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Recent Interactions */}
        {context?.interactions && context.interactions.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider mb-2">
              Recent Interactions
            </h4>
            <div className="space-y-1">
              {context.interactions.slice(0, 5).map((i) => (
                <div key={i.id} className="text-xs p-2 rounded bg-[var(--background-secondary)]">
                  <span className="font-medium">{i.interaction_type}</span>
                  {i.sentiment && (
                    <span className="ml-1 text-[var(--foreground-muted)]">({i.sentiment})</span>
                  )}
                  {i.summary && (
                    <p className="text-[var(--foreground-muted)] mt-0.5 truncate">{i.summary}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </ScrollArea>
  );
}
