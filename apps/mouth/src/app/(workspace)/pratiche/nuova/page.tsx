'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ArrowLeft, FolderKanban, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CreatePracticeParams } from '@/lib/api/crm/crm.types';

export default function NewPracticePage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<CreatePracticeParams>({
    title: '',
    practice_type_code: 'investor_kitas', // Default
    description: '',
    client_id: undefined,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const user = await api.getProfile();
      await api.crm.createPractice(formData, user.email);
      router.push('/pratiche');
    } catch (error) {
      console.error('Failed to create case', error);
      const message = error instanceof Error ? error.message : 'Unknown error';
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (error as any).detail;
      alert(`Failed to create case: ${detail || message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'client_id' ? parseInt(value) || undefined : value,
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/pratiche">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">New Case</h1>
          <p className="text-sm text-foreground-muted">Start a new practice or case</p>
        </div>
      </div>

      {/* Form */}
      <div className="rounded-xl border border-border bg-background-secondary p-8 max-w-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Case Title</label>
            <div className="relative">
              <FolderKanban className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
              <input
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                type="text"
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                placeholder="e.g. KITAS Renewal - John Doe"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Case Type</label>
            <select
              name="practice_type_code"
              value={formData.practice_type_code}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              <option value="investor_kitas">Investor KITAS</option>
              <option value="work_kitas">Work KITAS</option>
              <option value="business_visa">Business Visa</option>
              <option value="pt_pma">PT PMA Setup</option>
              <option value="tax_reporting">Tax Reporting</option>
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Client ID</label>
            <input
              name="client_id"
              value={formData.client_id || ''}
              onChange={handleChange}
              type="number"
              className="w-full px-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
              placeholder="Enter Client ID (e.g. 1)"
            />
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <Link href="/pratiche">
              <Button variant="outline" type="button" disabled={isLoading}>
                Cancel
              </Button>
            </Link>
            <Button
              className="bg-accent hover:bg-accent-hover text-white min-w-[120px]"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Case'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
