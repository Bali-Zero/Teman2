'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  Loader2,
  Building2,
  Globe,
  CreditCard,
  Calendar,
  MapPin,
  Tag,
  UserCheck,
  Briefcase,
  MessageSquare,
  ChevronDown,
  Check,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CreateClientParams } from '@/lib/api/crm/crm.types';
import {
  COMMON_NATIONALITIES,
  CLIENT_STATUSES,
  LEAD_SOURCES,
  SERVICE_INTERESTS,
} from '@/lib/api/crm/crm.types';

// Team members - ideally fetch from API
const TEAM_MEMBERS = [
  { value: 'ruslana@balizero.com', label: 'Ruslana' },
  { value: 'krisna@balizero.com', label: 'Krisna' },
  { value: 'veronika@balizero.com', label: 'Veronika' },
  { value: 'adit@balizero.com', label: 'Adit' },
  { value: 'zero@balizero.com', label: 'Antonello' },
];

export default function NewClientPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [activeSection, setActiveSection] = useState<'basic' | 'personal' | 'crm'>('basic');
  const [formData, setFormData] = useState<CreateClientParams>({
    full_name: '',
    email: '',
    phone: '',
    whatsapp: '',
    company_name: '',
    nationality: '',
    passport_number: '',
    passport_expiry: '',
    date_of_birth: '',
    notes: '',
    status: 'lead',
    client_type: 'individual',
    assigned_to: '',
    tags: [],
    address: '',
    lead_source: undefined,
    service_interest: [],
  });

  // Sync whatsapp with phone if not set
  useEffect(() => {
    if (formData.phone && !formData.whatsapp) {
      setFormData(prev => ({ ...prev, whatsapp: prev.phone }));
    }
  }, [formData.phone, formData.whatsapp]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const user = await api.getProfile();
      // Clean up empty arrays and undefined values
      const cleanData = {
        ...formData,
        tags: formData.tags?.length ? formData.tags : undefined,
        service_interest: formData.service_interest?.length ? formData.service_interest : undefined,
      };
      await api.crm.createClient(cleanData, user.email);
      router.push('/clients');
    } catch (error) {
      console.error('Failed to create client:', error);

      // Extract error message from various error formats
      let errorMessage = 'Failed to create client';

      if (error instanceof Error) {
        errorMessage = error.message;
        // Check if message contains JSON (from API response)
        if (error.message.includes('{"')) {
          try {
            const parsed = JSON.parse(error.message);
            errorMessage = parsed.detail || parsed.message || error.message;
          } catch {
            // Not JSON, use message as-is
          }
        }
      } else if (typeof error === 'object' && error !== null) {
        // Handle object errors (shouldn't happen but be defensive)
        const errObj = error as Record<string, unknown>;
        errorMessage = (errObj.detail as string) || (errObj.message as string) || 'Unknown error';
      }

      alert(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const toggleServiceInterest = (value: string) => {
    setFormData((prev) => ({
      ...prev,
      service_interest: prev.service_interest?.includes(value)
        ? prev.service_interest.filter((v) => v !== value)
        : [...(prev.service_interest || []), value],
    }));
  };

  const inputClass =
    'w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all';
  const selectClass =
    'w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 appearance-none cursor-pointer transition-all';
  const labelClass = 'text-sm font-medium text-[var(--foreground)] mb-1.5 block';

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/clients">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-[var(--foreground)]">New Client</h1>
          <p className="text-sm text-[var(--foreground-muted)]">Add a new client to the CRM</p>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-2 border-b border-[var(--border)] pb-2">
        {[
          { key: 'basic', label: 'Basic Info', icon: User },
          { key: 'personal', label: 'Personal Details', icon: CreditCard },
          { key: 'crm', label: 'CRM Settings', icon: Briefcase },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveSection(key as typeof activeSection)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeSection === key
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)]'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info Section */}
        {activeSection === 'basic' && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6 space-y-5">
            <h3 className="text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
              <User className="w-5 h-5 text-[var(--accent)]" />
              Contact Information
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Full Name */}
              <div className="md:col-span-2">
                <label className={labelClass}>
                  Full Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    required
                    type="text"
                    className={inputClass}
                    placeholder="John Doe"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className={labelClass}>Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    type="email"
                    className={inputClass}
                    placeholder="john@example.com"
                  />
                </div>
              </div>

              {/* Phone */}
              <div>
                <label className={labelClass}>Phone</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    type="tel"
                    className={inputClass}
                    placeholder="+62 812 3456 7890"
                  />
                </div>
              </div>

              {/* WhatsApp */}
              <div>
                <label className={labelClass}>WhatsApp</label>
                <div className="relative">
                  <MessageSquare className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-500" />
                  <input
                    name="whatsapp"
                    value={formData.whatsapp}
                    onChange={handleChange}
                    type="tel"
                    className={inputClass}
                    placeholder="Same as phone or different"
                  />
                </div>
              </div>

              {/* Client Type */}
              <div>
                <label className={labelClass}>Client Type</label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <select
                    name="client_type"
                    value={formData.client_type}
                    onChange={handleChange}
                    className={selectClass}
                  >
                    <option value="individual">Individual</option>
                    <option value="company">Company</option>
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Company Name (conditional) */}
              {formData.client_type === 'company' && (
                <div className="md:col-span-2">
                  <label className={labelClass}>Company Name</label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                    <input
                      name="company_name"
                      value={formData.company_name}
                      onChange={handleChange}
                      type="text"
                      className={inputClass}
                      placeholder="PT Example Indonesia"
                    />
                  </div>
                </div>
              )}

              {/* Address */}
              <div className="md:col-span-2">
                <label className={labelClass}>Address</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-3 w-4 h-4 text-[var(--foreground-muted)]" />
                  <textarea
                    name="address"
                    value={formData.address}
                    onChange={handleChange}
                    rows={2}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 resize-none"
                    placeholder="Jl. Example No. 123, Seminyak, Bali"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <Button
                type="button"
                onClick={() => setActiveSection('personal')}
                className="gap-2"
              >
                Next: Personal Details
                <ChevronDown className="w-4 h-4 rotate-[-90deg]" />
              </Button>
            </div>
          </div>
        )}

        {/* Personal Details Section */}
        {activeSection === 'personal' && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6 space-y-5">
            <h3 className="text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-[var(--accent)]" />
              Personal Details
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Nationality */}
              <div>
                <label className={labelClass}>Nationality</label>
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <select
                    name="nationality"
                    value={formData.nationality}
                    onChange={handleChange}
                    className={selectClass}
                  >
                    <option value="">Select nationality...</option>
                    {COMMON_NATIONALITIES.map((nat) => (
                      <option key={nat} value={nat}>
                        {nat}
                      </option>
                    ))}
                    <option value="other">Other</option>
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Date of Birth */}
              <div>
                <label className={labelClass}>Date of Birth</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="date_of_birth"
                    value={formData.date_of_birth}
                    onChange={handleChange}
                    type="date"
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Passport Number */}
              <div>
                <label className={labelClass}>Passport Number</label>
                <div className="relative">
                  <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="passport_number"
                    value={formData.passport_number}
                    onChange={handleChange}
                    type="text"
                    className={inputClass}
                    placeholder="AB1234567"
                  />
                </div>
              </div>

              {/* Passport Expiry */}
              <div>
                <label className={labelClass}>Passport Expiry</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <input
                    name="passport_expiry"
                    value={formData.passport_expiry}
                    onChange={handleChange}
                    type="date"
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Notes */}
              <div className="md:col-span-2">
                <label className={labelClass}>Notes</label>
                <textarea
                  name="notes"
                  value={formData.notes}
                  onChange={handleChange}
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 resize-none"
                  placeholder="Additional notes about the client..."
                />
              </div>
            </div>

            <div className="flex justify-between pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setActiveSection('basic')}
                className="gap-2"
              >
                <ChevronDown className="w-4 h-4 rotate-90" />
                Back
              </Button>
              <Button
                type="button"
                onClick={() => setActiveSection('crm')}
                className="gap-2"
              >
                Next: CRM Settings
                <ChevronDown className="w-4 h-4 rotate-[-90deg]" />
              </Button>
            </div>
          </div>
        )}

        {/* CRM Settings Section */}
        {activeSection === 'crm' && (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6 space-y-5">
            <h3 className="text-lg font-semibold text-[var(--foreground)] flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-[var(--accent)]" />
              CRM Settings
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Status */}
              <div>
                <label className={labelClass}>Status</label>
                <div className="relative">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <select
                    name="status"
                    value={formData.status}
                    onChange={handleChange}
                    className={selectClass}
                  >
                    {CLIENT_STATUSES.map((status) => (
                      <option key={status.value} value={status.value}>
                        {status.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Lead Source */}
              <div>
                <label className={labelClass}>Lead Source</label>
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <select
                    name="lead_source"
                    value={formData.lead_source || ''}
                    onChange={handleChange}
                    className={selectClass}
                  >
                    <option value="">Select source...</option>
                    {LEAD_SOURCES.map((source) => (
                      <option key={source.value} value={source.value}>
                        {source.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Assigned To */}
              <div>
                <label className={labelClass}>Assigned To</label>
                <div className="relative">
                  <UserCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                  <select
                    name="assigned_to"
                    value={formData.assigned_to}
                    onChange={handleChange}
                    className={selectClass}
                  >
                    <option value="">Unassigned</option>
                    {TEAM_MEMBERS.map((member) => (
                      <option key={member.value} value={member.value}>
                        {member.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)] pointer-events-none" />
                </div>
              </div>

              {/* Service Interest */}
              <div className="md:col-span-2">
                <label className={labelClass}>Service Interest</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {SERVICE_INTERESTS.map((service) => {
                    const isSelected = formData.service_interest?.includes(service.value);
                    return (
                      <button
                        key={service.value}
                        type="button"
                        onClick={() => toggleServiceInterest(service.value)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-1.5 ${
                          isSelected
                            ? 'bg-[var(--accent)] text-white'
                            : 'bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)]/80'
                        }`}
                      >
                        {isSelected ? (
                          <Check className="w-3.5 h-3.5" />
                        ) : (
                          <span className="w-3.5 h-3.5" />
                        )}
                        {service.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-4 border-t border-[var(--border)]">
              <Button
                type="button"
                variant="outline"
                onClick={() => setActiveSection('personal')}
                className="gap-2"
              >
                <ChevronDown className="w-4 h-4 rotate-90" />
                Back
              </Button>
              <div className="flex gap-3">
                <Link href="/clients">
                  <Button variant="outline" type="button" disabled={isLoading}>
                    Cancel
                  </Button>
                </Link>
                <Button
                  className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white min-w-[140px]"
                  type="submit"
                  disabled={isLoading || !formData.full_name}
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Check className="w-4 h-4 mr-2" />
                      Create Client
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Quick Summary Card */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-4">
          <h4 className="text-sm font-medium text-[var(--foreground-muted)] mb-3">Summary</h4>
          <div className="flex flex-wrap gap-3 text-sm">
            {formData.full_name && (
              <span className="px-2 py-1 rounded bg-[var(--background-elevated)] text-[var(--foreground)]">
                {formData.full_name}
              </span>
            )}
            {formData.status && (
              <span
                className={`px-2 py-1 rounded ${
                  formData.status === 'lead'
                    ? 'bg-blue-500/20 text-blue-400'
                    : formData.status === 'active'
                    ? 'bg-green-500/20 text-green-400'
                    : formData.status === 'completed'
                    ? 'bg-purple-500/20 text-purple-400'
                    : 'bg-gray-500/20 text-gray-400'
                }`}
              >
                {CLIENT_STATUSES.find((s) => s.value === formData.status)?.label}
              </span>
            )}
            {formData.nationality && (
              <span className="px-2 py-1 rounded bg-[var(--background-elevated)] text-[var(--foreground)]">
                {formData.nationality}
              </span>
            )}
            {formData.assigned_to && (
              <span className="px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)]">
                → {TEAM_MEMBERS.find((m) => m.value === formData.assigned_to)?.label}
              </span>
            )}
            {formData.service_interest && formData.service_interest.length > 0 && (
              <span className="px-2 py-1 rounded bg-purple-500/20 text-purple-400">
                {formData.service_interest.length} service(s)
              </span>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
