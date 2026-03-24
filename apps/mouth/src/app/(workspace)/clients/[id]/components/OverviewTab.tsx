'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  User,
  Edit2,
  Users,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ClientProfile, ClientDocument } from '@/lib/api/crm/crm.types';
import { formatPhoneNumber, isBirthdayToday } from './utils';
import { PassportCard } from './PassportCard';
import { VisaCard } from './VisaCard';

export function OverviewTab({
  client,
  stats,
  documents,
  activePractices,
  completedPractices,
  formatDate,
  formatCurrency,
  router,
  onEditClick,
  onRefresh,
  clientId,
}: {
  client: ClientProfile['client'];
  stats: ClientProfile['stats'];
  documents: ClientDocument[];
  activePractices: ClientProfile['practices'];
  completedPractices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
  onEditClick: () => void;
  onRefresh: () => Promise<void>;
  clientId: number;
}) {
  const isClientBirthday = isBirthdayToday(client.date_of_birth);

  return (
    <div className="space-y-6">
      {/* 3 Columns Layout - Team Member | Passport | Visa */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {/* COLUMN 1: Client Info */}
        <div className="flex flex-col h-full">
          {/* Client Info Card */}
          <div
            className="rounded-xl border shadow-xl backdrop-blur-xl transition-all duration-300 overflow-hidden flex-1 flex flex-col h-full hover:shadow-2xl hover:-translate-y-1"
            style={{
              border: '1px solid rgba(255, 255, 255, 0.05)',
              background: 'rgba(32, 32, 36, 0.65)',
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-3 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <h3 className="font-semibold text-[var(--bz-text-1)]">Client Info</h3>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={onEditClick}
                  aria-label="Edit client info"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
            <div className="p-4 space-y-4 flex-1">
              {/* Full Name */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-[var(--bz-accent)]/10 flex items-center justify-center">
                  <User className="w-4 h-4 text-[var(--bz-accent)]" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-[var(--bz-text-2)]">Full Name</p>
                  <p className="text-base font-semibold">{client.full_name}</p>
                </div>
              </div>

              <div className="border-t border-[var(--bz-border)]" />

              {/* Contact Info */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Email
                  </p>
                  <p className="text-sm font-medium truncate">
                    {client.email || (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Phone
                  </p>
                  <p className="text-sm font-medium">
                    {client.phone ? (
                      formatPhoneNumber(client.phone)
                    ) : (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Nationality
                  </p>
                  <p className="text-sm font-medium">
                    {client.nationality || (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Gender
                  </p>
                  <p className="text-sm font-medium">
                    {client.gender === 'M' ? (
                      'Male'
                    ) : client.gender === 'F' ? (
                      'Female'
                    ) : (
                      <span className="text-[var(--bz-text-2)] italic text-xs">—</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Passport & DOB - from OCR extraction */}
              {(client.passport_number || client.date_of_birth) && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    {client.passport_number && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Passport
                        </p>
                        <p className="text-sm font-semibold font-mono">{client.passport_number}</p>
                      </div>
                    )}
                    {client.passport_expiry && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Passport Expiry
                        </p>
                        <p
                          className={`text-sm font-medium ${new Date(client.passport_expiry) < new Date() ? 'text-red-500' : new Date(client.passport_expiry) < new Date(Date.now() + 365 * 86400000) ? 'text-yellow-500' : 'text-green-500'}`}
                        >
                          {formatDate(client.passport_expiry)}
                        </p>
                      </div>
                    )}
                    {client.date_of_birth && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Date of Birth
                        </p>
                        <p className="text-sm font-medium">{formatDate(client.date_of_birth)}</p>
                      </div>
                    )}
                    {client.birthplace && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                          Birthplace
                        </p>
                        <p className="text-sm font-medium">{client.birthplace}</p>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Address */}
              {client.address && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                      Address
                    </p>
                    <p className="text-sm font-medium">{client.address}</p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div
              className="rounded-lg border shadow-lg backdrop-blur-md p-3 transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
              style={{
                border: '1px solid rgba(255, 255, 255, 0.05)',
                background: 'rgba(35, 35, 40, 0.45)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <Users className="w-3.5 h-3.5 text-blue-500" />
                <span className="text-[10px] text-[var(--bz-text-2)]">Family</span>
              </div>
              <p className="text-lg font-bold">{stats.family_count}</p>
            </div>
            <div
              className="rounded-lg border shadow-lg backdrop-blur-md p-3 transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
              style={{
                border: '1px solid rgba(255, 255, 255, 0.05)',
                background: 'rgba(35, 35, 40, 0.45)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <FileText className="w-3.5 h-3.5 text-purple-500" />
                <span className="text-[10px] text-[var(--bz-text-2)]">Docs</span>
              </div>
              <p className="text-lg font-bold">{stats.documents_count}</p>
            </div>
          </div>
        </div>

        {/* COLUMN 2: Passport */}
        <div className="flex flex-col h-full">
          <PassportCard
            client={client}
            documents={documents}
            formatDate={formatDate}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>

        {/* COLUMN 3: Visa */}
        <div className="flex flex-col h-full">
          <VisaCard
            client={client}
            documents={documents}
            activePractices={activePractices}
            formatDate={formatDate}
            formatCurrency={formatCurrency}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>
      </div>
    </div>
  );
}
