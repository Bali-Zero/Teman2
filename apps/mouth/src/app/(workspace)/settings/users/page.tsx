'use client';

import React, { useState, useEffect } from 'react';
import { Users, Plus, Search, MoreVertical, Mail, Shield, ArrowLeft, UserCircle, CheckCircle2, XCircle } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

interface TeamMember {
  user_id: string;
  email: string;
  name: string;
  role: string;
  team: string;
  is_online: boolean;
  last_action: string;
}

export default function UserManagementPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [users, setUsers] = useState<TeamMember[]>([]);
  const [newUser, setNewUser] = useState({
    email: '',
    name: '',
    role: 'user',
    team: 'Team',
  });

  useEffect(() => {
    const loadUsers = async () => {
      try {
        const teamStatus = await api.getTeamStatus();
        setUsers(teamStatus.map(u => ({
          ...u,
          name: u.email.split('@')[0],
          role: u.email === 'zero@balizero.com' ? 'admin' : 'user',
          team: 'Team',
        })));
      } catch (err) {
        console.error('Failed to load users:', err);
        // Fallback mock data
        setUsers([
          { user_id: '1', email: 'zero@balizero.com', name: 'Zero', role: 'admin', team: 'Team', is_online: true, last_action: 'now' },
          { user_id: '2', email: 'staff@balizero.com', name: 'Staff', role: 'user', team: 'Team', is_online: false, last_action: '2h ago' },
        ]);
      } finally {
        setIsLoading(false);
      }
    };
    loadUsers();
  }, []);

  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAddUser = () => {
    // In a real app, this would call an API
    const newMember: TeamMember = {
      user_id: Date.now().toString(),
      ...newUser,
      is_online: false,
      last_action: 'Never',
    };
    setUsers([...users, newMember]);
    setShowAddModal(false);
    setNewUser({ email: '', name: '', role: 'user', team: 'Team' });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push('/settings')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
              <Users className="w-6 h-6 text-blue-400" />
              User Management
            </h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              Add, modify or remove users
            </p>
          </div>
        </div>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add User
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--foreground-muted)]" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search users..."
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Total Users</p>
          <p className="text-2xl font-bold text-[var(--foreground)]">{users.length}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Online Now</p>
          <p className="text-2xl font-bold text-green-400">{users.filter(u => u.is_online).length}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Admins</p>
          <p className="text-2xl font-bold text-purple-400">{users.filter(u => u.role === 'admin').length}</p>
        </div>
      </div>

      {/* Users Table */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <p className="text-sm text-[var(--foreground-muted)]">Loading users...</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--background)]">
                <th className="text-left p-4 text-sm font-medium text-[var(--foreground-muted)]">User</th>
                <th className="text-left p-4 text-sm font-medium text-[var(--foreground-muted)]">Role</th>
                <th className="text-left p-4 text-sm font-medium text-[var(--foreground-muted)]">Status</th>
                <th className="text-left p-4 text-sm font-medium text-[var(--foreground-muted)]">Last Active</th>
                <th className="text-right p-4 text-sm font-medium text-[var(--foreground-muted)]">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filteredUsers.map((user) => (
                <tr key={user.user_id} className="hover:bg-[var(--background)]/50">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-[var(--background)] flex items-center justify-center">
                        <UserCircle className="w-6 h-6 text-[var(--foreground-muted)]" />
                      </div>
                      <div>
                        <p className="font-medium text-[var(--foreground)]">{user.name}</p>
                        <p className="text-sm text-[var(--foreground-muted)]">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                      user.role === 'admin'
                        ? 'bg-purple-500/20 text-purple-400'
                        : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      <Shield className="w-3 h-3" />
                      {user.role}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1 text-sm ${
                      user.is_online ? 'text-green-400' : 'text-[var(--foreground-muted)]'
                    }`}>
                      {user.is_online ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : (
                        <XCircle className="w-4 h-4" />
                      )}
                      {user.is_online ? 'Online' : 'Offline'}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-[var(--foreground-muted)]">
                    {user.last_action}
                  </td>
                  <td className="p-4 text-right">
                    <Button variant="ghost" size="sm">
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-elevated)] p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Add New User</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                  placeholder="Full name"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <Mail className="w-4 h-4 inline mr-1" />
                  Email
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  placeholder="email@example.com"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Role
                </label>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <Button variant="ghost" onClick={() => setShowAddModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddUser}>
                  Add User
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
