"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Users, Clock, Calendar, UserCircle, Circle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

/** Dashboard panel recipe — mirrors the operative-dark kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "rgba(35,35,40,0.65)",
  borderColor: "var(--bz-border)",
};

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
  adit: "/static/team/adit.jpg",
  krisna: "/static/team/krisna.jpg",
  ari: "/static/team/ari.jpg",
  "ari.firda": "/static/team/ari.jpg",
  dea: "/static/team/dea.jpg",
  sahira: "/static/team/sahira.jpg",
  surya: "/static/team/surya.jpg",
  damar: "/static/team/damar.jpg",
  asya: "/static/team/asya.jpg",
  angel: "/static/team/angel.jpg",
  veronika: "/static/team/veronika.jpg",
  faisha: "/static/team/faisha.jpg",
  dewaayu: "/static/team/dewaayu.jpg",
  "dewa.ayu": "/static/team/dewaayu.jpg",
  candra: "/static/team/candra.jpg",
  subhi: "/static/team/subhi.jpg",
};

// Get photo URL from email
const getTeamPhoto = (email: string): string | null => {
  const prefix = email.split("@")[0].toLowerCase();
  return TEAM_PHOTOS[prefix] || null;
};

// Department mapping by email domain/prefix
const getDepartment = (email: string): string => {
  const prefix = email.split("@")[0].toLowerCase();
  if (["zero", "admin"].includes(prefix)) return "Management";
  if (["adit", "krisna", "reza", "adi", "dika", "wayan"].includes(prefix))
    return "Setup Team";
  if (["veronika", "tax", "accounting"].includes(prefix)) return "Tax Team";
  if (["consulting", "advisory"].includes(prefix)) return "Advisory";
  if (["marketing", "social", "content"].includes(prefix)) return "Marketing";
  return "Operations";
};

// Department identity dots — token hues, honestly mapped (identity, not status).
const teamDepartments = [
  { name: "Management", members: 2, color: "var(--bz-accent)" },
  { name: "Setup Team", members: 6, color: "var(--state-success)" },
  { name: "Tax Team", members: 4, color: "var(--state-info)" },
  { name: "Advisory", members: 3, color: "var(--state-warning)" },
  { name: "Operations", members: 5, color: "var(--bz-neon-purple)" },
  { name: "Marketing", members: 3, color: "var(--accent-pink-editorial)" },
];

function StatCard({
  label,
  value,
  valueStyle,
}: {
  label: string;
  value: React.ReactNode;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div
      className="p-4 rounded-xl border shadow-xl backdrop-blur-md transition-all hover:-translate-y-1 hover:shadow-2xl"
      style={PANEL}
    >
      <p className="text-sm text-[var(--bz-text-2)]">{label}</p>
      <p
        className="text-2xl font-bold text-[var(--bz-text-1)]"
        style={valueStyle}
      >
        {value}
      </p>
    </div>
  );
}

export default function TeamPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [onlineCount, setOnlineCount] = useState(0);
  const [totalMembers, setTotalMembers] = useState(23);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [filteredDept, setFilteredDept] = useState<string | null>(null);
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
          setOnlineCount(
            teamStatus.filter((m: TeamMember) => m.is_online).length,
          );
          setTotalMembers(teamStatus.length);
        } else {
          // Fallback: try clock status
          const clockStatus = await api.getClockStatus().catch(() => null);
          if (clockStatus?.is_clocked_in) {
            setOnlineCount(1);
          }
        }
      } catch (err) {
        logger.error("Failed to load team stats", {}, err as Error);
        setError("Failed to load team data");
      } finally {
        setIsLoading(false);
      }
    };

    loadTeamStats();
  }, []);

  const handleCalendar = () => {
    router.push("/team/analytics");
  };

  const handleTimesheet = () => {
    toast("Timesheet coming soon", {
      description:
        "The full timesheet view will be available in a future update.",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--bz-text-1)]">Team</h1>
          <p className="text-sm text-[var(--bz-text-2)]">
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
        <StatCard label="Team Members" value={isLoading ? "-" : totalMembers} />
        <StatCard
          label="Online Now"
          value={isLoading ? "-" : onlineCount}
          valueStyle={{ color: "var(--state-success)" }}
        />
        <StatCard label="On Leave" value="0" />
        <StatCard label="Hours Today" value="0h" />
      </div>

      {/* Departments Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {teamDepartments.map((dept) => (
          <div
            key={dept.name}
            onClick={() =>
              setFilteredDept(filteredDept === dept.name ? null : dept.name)
            }
            className={`p-4 rounded-xl border shadow-xl backdrop-blur-md cursor-pointer transition-all hover:shadow-2xl hover:-translate-y-1 ${
              filteredDept === dept.name
                ? "border-[var(--bz-accent)] ring-1 ring-[var(--bz-accent)]"
                : "border-[var(--bz-border)]"
            }`}
            style={{ background: PANEL.background }}
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: dept.color }}
              />
              <h3 className="font-medium text-[var(--bz-text-1)]">
                {dept.name}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-[var(--bz-text-2)]" />
              <span className="text-sm text-[var(--bz-text-2)]">
                {dept.members} members
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Team Members List */}
      <div
        className="rounded-xl border shadow-2xl backdrop-blur-xl"
        style={PANEL}
      >
        <div className="p-4 border-b border-[var(--bz-border)] flex items-center justify-between">
          <h2 className="font-semibold text-[var(--bz-text-1)]">
            {filteredDept ? `${filteredDept} Members` : "Team Members"}
          </h2>
          {filteredDept && (
            <button
              onClick={() => setFilteredDept(null)}
              className="text-xs text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors"
            >
              Clear filter ×
            </button>
          )}
        </div>
        {isLoading ? (
          <div className="p-8 text-center">
            <UserCircle className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50 animate-pulse" />
            <p className="text-sm text-[var(--bz-text-2)]">
              Loading team members...
            </p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[var(--state-danger)]">{error}</p>
          </div>
        ) : teamMembers.length === 0 ? (
          <div className="p-8 text-center">
            <UserCircle className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
            <p className="text-sm text-[var(--bz-text-2)]">
              No team members have clocked in yet today.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--bz-border)]">
            {teamMembers
              .filter(
                (m) => !filteredDept || getDepartment(m.email) === filteredDept,
              )
              .map((member) => (
                <div
                  key={member.user_id}
                  className="p-4 flex items-center justify-between hover:bg-[var(--bz-glass-rim)] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      {getTeamPhoto(member.email) ? (
                        <Image
                          src={getTeamPhoto(member.email)!}
                          alt={member.email.split("@")[0]}
                          width={40}
                          height={40}
                          className="w-10 h-10 rounded-full object-cover"
                        />
                      ) : (
                        <UserCircle className="w-10 h-10 text-[var(--bz-text-2)]" />
                      )}
                      <Circle
                        className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 ${
                          member.is_online
                            ? "text-[var(--state-success)] fill-[var(--state-success)]"
                            : "text-[var(--bz-text-3)] fill-[var(--bz-text-3)]"
                        }`}
                      />
                    </div>
                    <div>
                      <p className="font-medium text-[var(--bz-text-1)]">
                        {member.email.split("@")[0].charAt(0).toUpperCase() +
                          member.email.split("@")[0].slice(1)}
                      </p>
                      <p className="text-xs text-[var(--bz-text-2)]">
                        {getDepartment(member.email)} • {member.email}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p
                      className={`text-sm font-medium ${member.is_online ? "text-[var(--state-success)]" : "text-[var(--bz-text-2)]"}`}
                    >
                      {member.is_online ? "Online" : "Offline"}
                    </p>
                    <p className="text-xs text-[var(--bz-text-2)]">
                      {member.last_action_type === "clock_in"
                        ? "Clocked in"
                        : "Clocked out"}{" "}
                      • {member.last_action}
                    </p>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Info Box */}
      <div
        className="rounded-xl border border-dashed border-[var(--bz-border)] backdrop-blur-sm p-8 text-center"
        style={{ background: PANEL.background }}
      >
        <p className="text-sm text-[var(--bz-text-2)] max-w-md mx-auto">
          Manage the Bali Zero team with attendance, timesheet, leave and
          permissions. View who is online and hours worked.
        </p>
      </div>
    </div>
  );
}
