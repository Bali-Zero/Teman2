'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Calendar, Send } from 'lucide-react';
import * as hrApi from '@/lib/api/hr/hr';

export default function LeaveRequestPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    leave_type_id: 1,
    start_date: '',
    end_date: '',
    total_days: 1,
    reason: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await hrApi.requestLeave(form);
      router.push('/hr/leave');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  // Auto-calculate days when dates change
  const updateDays = (start: string, end: string) => {
    if (start && end) {
      const diff = Math.ceil(
        (new Date(end).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24)
      ) + 1;
      setForm(prev => ({ ...prev, start_date: start, end_date: end, total_days: Math.max(1, diff) }));
    }
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">Request Leave</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Leave Type</label>
          <select
            value={form.leave_type_id}
            onChange={e => setForm(prev => ({ ...prev, leave_type_id: Number(e.target.value) }))}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200"
          >
            <option value={1}>Annual Leave</option>
            <option value={2}>Sick Leave</option>
            <option value={3}>Maternity Leave</option>
            <option value={4}>Paternity Leave</option>
            <option value={5}>Marriage Leave</option>
            <option value={6}>Bereavement</option>
            <option value={7}>Unpaid Leave</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Start Date</label>
            <input
              type="date"
              value={form.start_date}
              onChange={e => updateDays(e.target.value, form.end_date)}
              required
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200"
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">End Date</label>
            <input
              type="date"
              value={form.end_date}
              onChange={e => updateDays(form.start_date, e.target.value)}
              required
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">
            Total Days: <span className="text-zinc-200 font-medium">{form.total_days}</span>
          </label>
        </div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">Reason (optional)</label>
          <textarea
            value={form.reason}
            onChange={e => setForm(prev => ({ ...prev, reason: e.target.value }))}
            rows={3}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200"
            placeholder="Why do you need this leave?"
          />
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)] text-zinc-950 hover:opacity-90 text-sm font-medium transition-opacity disabled:opacity-50"
        >
          <Send size={16} />
          {submitting ? 'Submitting...' : 'Submit Request'}
        </button>
      </form>
    </div>
  );
}
