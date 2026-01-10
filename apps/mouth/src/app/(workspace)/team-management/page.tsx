'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Users, Clock, Calendar, UserCircle, Circle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

// Team member interface
interface TeamMember {
  user_id: string;
  email: string;
  is_online: boolean;
  last_action: string;
  last_action_type: string;
  name?: string;
  role?: string;
  department?: string;
}

// Team photos mapping (email prefix -> photo path)
const TEAM_PHOTOS: Record<string, string> = {
  adit: '/static/team/adit.png',
  krisna: '/static/team/krisna.png',
  ari: '/static/team/ari.png',
  'ari.firda': '/static/team/ari.png',
  dea: '/static/team/dea.png',
  sahira: '/static/team/sahira.png',
};

// Get photo URL from email
const getTeamPhoto = (email: string): string | null => {
  const prefix = email.split('@')[0].toLowerCase();
  return TEAM_PHOTOS[prefix] || null;
};

// Department mapping by email domain/prefix
const getDepartment = (email: string): string => {
  const prefix = email.split('@')[0].toLowerCase();
  if (['zero', 'admin'].includes(prefix)) return 'Management';
  if (['adit', 'krisna', 'reza', 'adi', 'dika', 'wayan'].includes(prefix)) return 'Setup Team';
  if (['veronika', 'tax', 'accounting'].includes(prefix)) return 'Tax Team';
  if (['consulting', 'advisory'].includes(prefix)) return 'Advisory';
  if (['marketing', 'social', 'content'].includes(prefix)) return 'Marketing';
  return 'Operations';
};

// Mock team data for departments
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
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTeamStats = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Load team status from API
        const teamStatus = await api.getTeamStatus().catch(() => null);

        if (teamStatus && Array.isArray(teamStatus)) {
          setTeamMembers(teamStatus);
          setOnlineCount(teamStatus.filter((m: TeamMember) => m.is_online).length);
          setTotalMembers(teamStatus.length);
        } else {
          // Fallback: try clock status
          const clockStatus = await api.getClockStatus().catch(() => null);
          if (clockStatus?.is_clocked_in) {
            setOnlineCount(1);
          }
        }
      } catch (err) {
        console.error('Failed to load team stats:', err);
        setError('Failed to load team data');
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

      {/* Team Members List */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-semibold text-[var(--foreground)]">Team Members</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center">
            <UserCircle className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50 animate-pulse" />
            <p className="text-sm text-[var(--foreground-muted)]">
              Loading team members...
            </p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        ) : teamMembers.length === 0 ? (
          <div className="p-8 text-center">
            <UserCircle className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
            <p className="text-sm text-[var(--foreground-muted)]">
              No team members have clocked in yet today.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {teamMembers.map((member) => (
              <div
                key={member.user_id}
                className="p-4 flex items-center justify-between hover:bg-[var(--background-elevated)]/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="relative">
                    {getTeamPhoto(member.email) ? (
                      <Image
                        src={getTeamPhoto(member.email)!}
                        alt={member.email.split('@')[0]}
                        width={40}
                        height={40}
                        className="w-10 h-10 rounded-full object-cover"
                      />
                    ) : (
                      <UserCircle className="w-10 h-10 text-[var(--foreground-muted)]" />
                    )}
                    <Circle
                      className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 ${
                        member.is_online ? 'text-green-500 fill-green-500' : 'text-gray-500 fill-gray-500'
                      }`}
                    />
                  </div>
                  <div>
                    <p className="font-medium text-[var(--foreground)]">
                      {member.email.split('@')[0].charAt(0).toUpperCase() + member.email.split('@')[0].slice(1)}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      {getDepartment(member.email)} • {member.email}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${member.is_online ? 'text-green-500' : 'text-[var(--foreground-muted)]'}`}>
                    {member.is_online ? 'Online' : 'Offline'}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">
                    {member.last_action_type === 'clock_in' ? 'Clocked in' : 'Clocked out'} • {member.last_action}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
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
