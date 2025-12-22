'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Users, Clock, Calendar, UserCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

// Mock team data
const teamDepartments = [
  { name: 'Management', members: 2, color: 'var(--accent)' },
  { name: 'Setup Team', members: 6, color: '#22c55e' },
  { name: 'Tax Team', members: 4, color: '#3b82f6' },
  { name: 'Advisory', members: 3, color: '#f59e0b' },
  { name: 'Operations', members: 5, color: '#8b5cf6' },
  { name: 'Marketing', members: 3, color: '#ec4899' },
];

export default function TeamPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [onlineCount, setOnlineCount] = useState(0);
  const [totalMembers, setTotalMembers] = useState(23);

  useEffect(() => {
    const loadTeamStats = async () => {
      setIsLoading(true);
      try {
        // Load clock status to get online count
        const clockStatus = await api.getClockStatus().catch(() => null);
        // For now, use mock data - real team API can be added later
        setOnlineCount(0);
        setTotalMembers(23);
      } catch (error) {
        console.error('Failed to load team stats:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadTeamStats();
  }, []);

  const handleCalendar = () => {
    // router.push('/team/calendar'); // TODO: Implement calendar page
    router.push('/team');
  };

  const handleTimesheet = () => {
    // router.push('/team/timesheet'); // TODO: Implement timesheet page
    router.push('/team');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Team</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Team management, attendance and timesheet
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2" onClick={handleCalendar}>
            <Calendar className="w-4 h-4" />
            Calendar
          </Button>
          <Button variant="outline" className="gap-2" onClick={handleTimesheet}>
            <Clock className="w-4 h-4" />
            Timesheet
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <p className="text-sm text-[var(--foreground-muted)]">Team Members</p>
          <p className="text-2xl font-bold text-[var(--foreground)]">
            {isLoading ? '-' : totalMembers}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <p className="text-sm text-[var(--foreground-muted)]">Online Now</p>
          <p className="text-2xl font-bold text-[var(--success)]">
            {isLoading ? '-' : onlineCount}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <p className="text-sm text-[var(--foreground-muted)]">On Leave</p>
          <p className="text-2xl font-bold text-[var(--foreground)]">0</p>
        </div>
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <p className="text-sm text-[var(--foreground-muted)]">Hours Today</p>
          <p className="text-2xl font-bold text-[var(--foreground)]">0h</p>
        </div>
      </div>

      {/* Departments Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {teamDepartments.map((dept) => (
          <div
            key={dept.name}
            onClick={() => {
              // Filter team members by department - can be implemented with real API
              console.log(`Filter by ${dept.name}`);
            }}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)]/50 cursor-pointer transition-colors"
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: dept.color }}
              />
              <h3 className="font-medium text-[var(--foreground)]">{dept.name}</h3>
            </div>
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-[var(--foreground-muted)]" />
              <span className="text-sm text-[var(--foreground-muted)]">
                {dept.members} members
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Team Members Placeholder */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-semibold text-[var(--foreground)]">Team Members</h2>
        </div>
        <div className="p-8 text-center">
          <UserCircle className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-sm text-[var(--foreground-muted)]">
            Loading team members...
          </p>
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Manage the Bali Zero team with attendance, timesheet, leave and permissions.
          View who is online and hours worked.
        </p>
      </div>
    </div>
  );
}
