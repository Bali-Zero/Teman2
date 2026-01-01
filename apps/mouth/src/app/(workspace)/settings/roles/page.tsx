'use client';

import React, { useState } from 'react';
import { Shield, Plus, Check, X, ArrowLeft, Users, Key, Eye, Edit, Trash2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

interface Permission {
  id: string;
  name: string;
  description: string;
}

interface Role {
  id: string;
  name: string;
  description: string;
  color: string;
  userCount: number;
  permissions: string[];
}

const allPermissions: Permission[] = [
  { id: 'dashboard_view', name: 'View Dashboard', description: 'Access to dashboard' },
  { id: 'chat_use', name: 'Use Zantara AI', description: 'Chat with AI assistant' },
  { id: 'clients_view', name: 'View Clients', description: 'View client list' },
  { id: 'clients_edit', name: 'Edit Clients', description: 'Create and modify clients' },
  { id: 'cases_view', name: 'View Cases', description: 'View case list' },
  { id: 'cases_edit', name: 'Edit Cases', description: 'Create and modify cases' },
  { id: 'knowledge_view', name: 'View Knowledge', description: 'Access knowledge base' },
  { id: 'knowledge_edit', name: 'Edit Knowledge', description: 'Add/edit knowledge documents' },
  { id: 'team_view', name: 'View Team', description: 'View team members' },
  { id: 'analytics_view', name: 'View Analytics', description: 'Access analytics dashboard' },
  { id: 'settings_view', name: 'View Settings', description: 'Access settings' },
  { id: 'settings_admin', name: 'Admin Settings', description: 'Manage users, roles, integrations' },
];

export default function RolesPermissionsPage() {
  const router = useRouter();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [newRole, setNewRole] = useState({
    name: '',
    description: '',
    color: '#60A5FA',
    permissions: [] as string[],
  });

  const [roles, setRoles] = useState<Role[]>([
    {
      id: '1',
      name: 'Admin',
      description: 'Full system access',
      color: '#A78BFA',
      userCount: 1,
      permissions: allPermissions.map(p => p.id),
    },
    {
      id: '2',
      name: 'User',
      description: 'Standard user access',
      color: '#60A5FA',
      userCount: 3,
      permissions: ['dashboard_view', 'chat_use', 'clients_view', 'cases_view', 'knowledge_view', 'settings_view'],
    },
    {
      id: '3',
      name: 'Viewer',
      description: 'Read-only access',
      color: '#34D399',
      userCount: 2,
      permissions: ['dashboard_view', 'clients_view', 'cases_view', 'knowledge_view'],
    },
  ]);

  const togglePermission = (permId: string) => {
    if (editingRole) {
      const hasPermission = editingRole.permissions.includes(permId);
      setEditingRole({
        ...editingRole,
        permissions: hasPermission
          ? editingRole.permissions.filter(p => p !== permId)
          : [...editingRole.permissions, permId],
      });
    } else {
      const hasPermission = newRole.permissions.includes(permId);
      setNewRole({
        ...newRole,
        permissions: hasPermission
          ? newRole.permissions.filter(p => p !== permId)
          : [...newRole.permissions, permId],
      });
    }
  };

  const handleSaveRole = () => {
    if (editingRole) {
      setRoles(roles.map(r => r.id === editingRole.id ? editingRole : r));
      setEditingRole(null);
    } else {
      const role: Role = {
        id: Date.now().toString(),
        ...newRole,
        userCount: 0,
      };
      setRoles([...roles, role]);
      setShowCreateModal(false);
      setNewRole({ name: '', description: '', color: '#60A5FA', permissions: [] });
    }
  };

  const deleteRole = (id: string) => {
    if (confirm('Are you sure you want to delete this role?')) {
      setRoles(roles.filter(r => r.id !== id));
    }
  };

  const currentPermissions = editingRole ? editingRole.permissions : newRole.permissions;

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
              <Shield className="w-6 h-6 text-purple-400" />
              Roles & Permissions
            </h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              Configure roles and their permissions
            </p>
          </div>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Role
        </Button>
      </div>

      {/* Roles List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {roles.map((role) => (
          <div
            key={role.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: `${role.color}20` }}
                >
                  <Shield className="w-5 h-5" style={{ color: role.color }} />
                </div>
                <div>
                  <h3 className="font-medium text-[var(--foreground)]">{role.name}</h3>
                  <p className="text-xs text-[var(--foreground-muted)]">{role.description}</p>
                </div>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => setEditingRole(role)}
                  className="p-1.5 rounded hover:bg-[var(--background)] text-[var(--foreground-muted)]"
                >
                  <Edit className="w-4 h-4" />
                </button>
                {role.name !== 'Admin' && (
                  <button
                    onClick={() => deleteRole(role.id)}
                    className="p-1.5 rounded hover:bg-red-500/20 text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1 text-[var(--foreground-muted)]">
                <Users className="w-4 h-4" />
                <span>{role.userCount} users</span>
              </div>
              <div className="flex items-center gap-1 text-[var(--foreground-muted)]">
                <Key className="w-4 h-4" />
                <span>{role.permissions.length} permissions</span>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-[var(--border)]">
              <div className="flex flex-wrap gap-1">
                {role.permissions.slice(0, 4).map((permId) => {
                  const perm = allPermissions.find(p => p.id === permId);
                  return (
                    <span
                      key={permId}
                      className="px-2 py-0.5 text-xs rounded-full bg-[var(--background)] text-[var(--foreground-muted)]"
                    >
                      {perm?.name}
                    </span>
                  );
                })}
                {role.permissions.length > 4 && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-[var(--background)] text-[var(--foreground-muted)]">
                    +{role.permissions.length - 4} more
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Permissions Matrix Info */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
        <h3 className="font-semibold text-[var(--foreground)] mb-2">Permission Categories</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-blue-400" />
            <span className="text-[var(--foreground-muted)]">View = Read access</span>
          </div>
          <div className="flex items-center gap-2">
            <Edit className="w-4 h-4 text-amber-400" />
            <span className="text-[var(--foreground-muted)]">Edit = Write access</span>
          </div>
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-purple-400" />
            <span className="text-[var(--foreground-muted)]">Admin = Full control</span>
          </div>
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-green-400" />
            <span className="text-[var(--foreground-muted)]">Use = Feature access</span>
          </div>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingRole) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-elevated)] p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">
              {editingRole ? 'Edit Role' : 'Create New Role'}
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                    Role Name
                  </label>
                  <input
                    type="text"
                    value={editingRole ? editingRole.name : newRole.name}
                    onChange={(e) => editingRole
                      ? setEditingRole({ ...editingRole, name: e.target.value })
                      : setNewRole({ ...newRole, name: e.target.value })
                    }
                    placeholder="e.g., Manager"
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                    Color
                  </label>
                  <input
                    type="color"
                    value={editingRole ? editingRole.color : newRole.color}
                    onChange={(e) => editingRole
                      ? setEditingRole({ ...editingRole, color: e.target.value })
                      : setNewRole({ ...newRole, color: e.target.value })
                    }
                    className="w-full h-10 rounded-lg cursor-pointer"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Description
                </label>
                <input
                  type="text"
                  value={editingRole ? editingRole.description : newRole.description}
                  onChange={(e) => editingRole
                    ? setEditingRole({ ...editingRole, description: e.target.value })
                    : setNewRole({ ...newRole, description: e.target.value })
                  }
                  placeholder="Brief description of this role"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-3">
                  Permissions
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {allPermissions.map((perm) => {
                    const isChecked = currentPermissions.includes(perm.id);
                    return (
                      <button
                        key={perm.id}
                        onClick={() => togglePermission(perm.id)}
                        className={`flex items-center gap-3 p-3 rounded-lg border transition-all text-left ${
                          isChecked
                            ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                            : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded flex items-center justify-center ${
                          isChecked ? 'bg-[var(--accent)]' : 'bg-[var(--background-secondary)] border border-[var(--border)]'
                        }`}>
                          {isChecked && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <div>
                          <p className={`text-sm font-medium ${isChecked ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                            {perm.name}
                          </p>
                          <p className="text-xs text-[var(--foreground-muted)]">{perm.description}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex gap-2 justify-end pt-4">
                <Button variant="ghost" onClick={() => {
                  setShowCreateModal(false);
                  setEditingRole(null);
                }}>
                  Cancel
                </Button>
                <Button onClick={handleSaveRole}>
                  {editingRole ? 'Save Changes' : 'Create Role'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
