'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ArrowLeft, User, Mail, Phone, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CreateClientParams } from '@/lib/api/crm/crm.types';

export default function NewClientPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<CreateClientParams>({
    full_name: '',
    email: '',
    phone: '',
    company_name: '',
    nationality: '',
    passport_number: '',
    notes: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const user = await api.getProfile();
      await api.crm.createClient(formData, user.email);
      // Ideally show toast here
      router.push('/clienti');
    } catch (error) {
      console.error('Failed to create client', error);
      const message = error instanceof Error ? error.message : 'Unknown error';
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (error as any).detail;
      alert(`Failed to create client: ${detail || message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/clienti">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">New Client</h1>
          <p className="text-sm text-foreground-muted">Add a new client to the registry</p>
        </div>
      </div>

      {/* Form */}
      <div className="rounded-xl border border-border bg-background-secondary p-8 max-w-2xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Full Name</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
              <input
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                required
                type="text"
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                placeholder="John Doe"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
              <input
                name="email"
                value={formData.email}
                onChange={handleChange}
                type="email"
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                placeholder="john@example.com"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Phone</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
              <input
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                type="tel"
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background-elevated text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                placeholder="+62..."
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <Link href="/clienti">
              <Button variant="outline" type="button" disabled={isLoading}>
                Cancel
              </Button>
            </Link>
            <Button
              className="bg-accent hover:bg-accent-hover text-white min-w-[120px]"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Client'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
