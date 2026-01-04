'use client';

import { useState, useEffect } from 'react';
import { X, Users, Plus, Trash2, Loader2, Shield, Eye, Pencil, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { FileItem, PermissionItem, PermissionRole } from '@/lib/api/drive/drive.types';

interface PermissionDialogProps {
  isOpen: boolean;
  file: FileItem | null;
  onClose: () => void;
}

const ROLE_OPTIONS: { value: PermissionRole; label: string; icon: React.ReactNode; description: string }[] = [
  { value: 'reader', label: 'Visualizzatore', icon: <Eye className="h-4 w-4" />, description: 'Può solo visualizzare' },
  { value: 'commenter', label: 'Commentatore', icon: <MessageSquare className="h-4 w-4" />, description: 'Può visualizzare e commentare' },
  { value: 'writer', label: 'Editor', icon: <Pencil className="h-4 w-4" />, description: 'Può modificare' },
  { value: 'owner', label: 'Proprietario', icon: <Shield className="h-4 w-4" />, description: 'Controllo completo' },
];

export function PermissionDialog({ isOpen, file, onClose }: PermissionDialogProps) {
  const [permissions, setPermissions] = useState<PermissionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add permission form
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<PermissionRole>('reader');
  const [sendNotification, setSendNotification] = useState(true);
  const [adding, setAdding] = useState(false);

  // For editing role
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Load permissions when dialog opens
  useEffect(() => {
    if (isOpen && file) {
      setError(null);
      loadPermissions();
    }
  }, [isOpen, file]);

  const loadPermissions = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const perms = await api.drive.listPermissions(file.id);
      setPermissions(perms);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nel caricamento permessi');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPermission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !newEmail.trim()) return;

    setAdding(true);
    setError(null);

    try {
      const newPerm = await api.drive.addPermission(file.id, {
        email: newEmail.trim(),
        role: newRole,
        send_notification: sendNotification,
      });
      setPermissions([...permissions, newPerm]);
      setNewEmail('');
      setNewRole('reader');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nell\'aggiunta del permesso');
    } finally {
      setAdding(false);
    }
  };

  const handleUpdateRole = async (permissionId: string, newRole: PermissionRole) => {
    if (!file) return;

    setEditingId(permissionId);
    setError(null);

    try {
      const updated = await api.drive.updatePermission(file.id, permissionId, { role: newRole });
      setPermissions(permissions.map(p => p.id === permissionId ? updated : p));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nell\'aggiornamento del ruolo');
    } finally {
      setEditingId(null);
    }
  };

  const handleRemovePermission = async (permissionId: string) => {
    if (!file) return;
    if (!confirm('Sei sicuro di voler rimuovere questo accesso?')) return;

    setDeletingId(permissionId);
    setError(null);

    try {
      await api.drive.removePermission(file.id, permissionId);
      setPermissions(permissions.filter(p => p.id !== permissionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nella rimozione del permesso');
    } finally {
      setDeletingId(null);
    }
  };

  const getRoleDisplay = (role: PermissionRole) => {
    const option = ROLE_OPTIONS.find(r => r.value === role);
    return option || ROLE_OPTIONS[0];
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--background)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
              <Users className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)]">Gestisci accesso</h2>
              <p className="max-w-[280px] truncate text-sm text-[var(--foreground-muted)]">
                {file?.name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-[var(--foreground-muted)] transition-colors hover:bg-[var(--background-secondary)] hover:text-[var(--foreground)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          {/* Error */}
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-500">
              {error}
            </div>
          )}

          {/* Add Permission Form */}
          <form onSubmit={handleAddPermission} className="mb-6">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Aggiungi persona
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="email@esempio.com"
                className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                disabled={adding}
              />
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as PermissionRole)}
                className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                disabled={adding}
              >
                {ROLE_OPTIONS.filter(r => r.value !== 'owner').map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <Button type="submit" disabled={adding || !newEmail.trim()}>
                {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              </Button>
            </div>
            <label className="mt-2 flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
              <input
                type="checkbox"
                checked={sendNotification}
                onChange={(e) => setSendNotification(e.target.checked)}
                className="rounded border-gray-300"
                disabled={adding}
              />
              Invia notifica via email
            </label>
          </form>

          {/* Current Permissions */}
          <div>
            <h3 className="mb-3 text-sm font-medium text-[var(--foreground)]">
              Chi ha accesso
            </h3>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
              </div>
            ) : permissions.length === 0 ? (
              <p className="py-4 text-center text-sm text-[var(--foreground-muted)]">
                Nessun permesso configurato
              </p>
            ) : (
              <div className="space-y-2">
                {permissions.map((perm) => {
                  const roleInfo = getRoleDisplay(perm.role);
                  const isEditing = editingId === perm.id;
                  const isDeleting = deletingId === perm.id;
                  const isOwner = perm.role === 'owner';

                  return (
                    <div
                      key={perm.id}
                      className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] px-4 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-purple-500 text-sm font-medium text-white">
                          {perm.name?.[0]?.toUpperCase() || perm.email?.[0]?.toUpperCase() || '?'}
                        </div>
                        <div>
                          <p className="font-medium text-[var(--foreground)]">
                            {perm.name || perm.email}
                          </p>
                          <p className="text-xs text-[var(--foreground-muted)]">
                            {perm.email}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {isEditing ? (
                          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        ) : isOwner ? (
                          <div className="flex items-center gap-1 rounded-lg bg-amber-500/10 px-3 py-1.5 text-sm text-amber-600">
                            <Shield className="h-4 w-4" />
                            Proprietario
                          </div>
                        ) : (
                          <select
                            value={perm.role}
                            onChange={(e) => handleUpdateRole(perm.id, e.target.value as PermissionRole)}
                            className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                          >
                            {ROLE_OPTIONS.filter(r => r.value !== 'owner').map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        )}

                        {!isOwner && (
                          <button
                            onClick={() => handleRemovePermission(perm.id)}
                            disabled={isDeleting}
                            className="rounded-lg p-2 text-[var(--foreground-muted)] transition-colors hover:bg-red-500/10 hover:text-red-500 disabled:opacity-50"
                          >
                            {isDeleting ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-[var(--border)] px-6 py-4">
          <Button variant="outline" onClick={onClose}>
            Chiudi
          </Button>
        </div>
      </div>
    </div>
  );
}
