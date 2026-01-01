'use client';

import React, { useState } from 'react';
import { Key, Copy, Eye, EyeOff, Plus, Trash2, ArrowLeft, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: string;
  lastUsed: string | null;
  permissions: string[];
}

export default function ApiKeysSettingsPage() {
  const router = useRouter();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const [apiKeys, setApiKeys] = useState<ApiKey[]>([
    {
      id: '1',
      name: 'Production API Key',
      key: 'zk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
      createdAt: '2024-01-15',
      lastUsed: '2024-12-28',
      permissions: ['read', 'write'],
    },
    {
      id: '2',
      name: 'Development Key',
      key: 'zk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
      createdAt: '2024-03-20',
      lastUsed: null,
      permissions: ['read'],
    },
  ]);

  const toggleKeyVisibility = (id: string) => {
    const newVisible = new Set(visibleKeys);
    if (newVisible.has(id)) {
      newVisible.delete(id);
    } else {
      newVisible.add(id);
    }
    setVisibleKeys(newVisible);
  };

  const copyToClipboard = async (key: string, id: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const deleteKey = (id: string) => {
    if (confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      setApiKeys(apiKeys.filter(k => k.id !== id));
    }
  };

  const createNewKey = () => {
    if (!newKeyName.trim()) return;

    const newKey: ApiKey = {
      id: Date.now().toString(),
      name: newKeyName,
      key: `zk_live_${Math.random().toString(36).substring(2, 35)}`,
      createdAt: new Date().toISOString().split('T')[0],
      lastUsed: null,
      permissions: ['read', 'write'],
    };

    setApiKeys([...apiKeys, newKey]);
    setNewKeyName('');
    setShowCreateModal(false);
  };

  const maskKey = (key: string) => {
    const prefix = key.substring(0, 8);
    return `${prefix}${'•'.repeat(24)}`;
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push('/settings')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
              <Key className="w-6 h-6 text-amber-400" />
              API Keys
            </h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              Manage your API keys for external integrations
            </p>
          </div>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Key
        </Button>
      </div>

      {/* Warning */}
      <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-yellow-500">Keep your API keys secure</h3>
            <p className="text-sm text-yellow-500/80">
              Never share your API keys or commit them to version control. Treat them like passwords.
            </p>
          </div>
        </div>
      </div>

      {/* API Keys List */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] overflow-hidden">
        <div className="divide-y divide-[var(--border)]">
          {apiKeys.length === 0 ? (
            <div className="p-8 text-center">
              <Key className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">No API keys created yet</p>
            </div>
          ) : (
            apiKeys.map((apiKey) => (
              <div key={apiKey.id} className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-medium text-[var(--foreground)]">{apiKey.name}</h3>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      Created: {apiKey.createdAt} • Last used: {apiKey.lastUsed || 'Never'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {apiKey.permissions.map((perm) => (
                      <span
                        key={perm}
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          perm === 'write'
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-blue-500/20 text-blue-400'
                        }`}
                      >
                        {perm}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--background)] font-mono text-sm">
                  <span className="flex-1 text-[var(--foreground-muted)]">
                    {visibleKeys.has(apiKey.id) ? apiKey.key : maskKey(apiKey.key)}
                  </span>
                  <button
                    onClick={() => toggleKeyVisibility(apiKey.id)}
                    className="p-1.5 rounded hover:bg-[var(--background-secondary)] text-[var(--foreground-muted)]"
                    title={visibleKeys.has(apiKey.id) ? 'Hide' : 'Show'}
                  >
                    {visibleKeys.has(apiKey.id) ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => copyToClipboard(apiKey.key, apiKey.id)}
                    className="p-1.5 rounded hover:bg-[var(--background-secondary)] text-[var(--foreground-muted)]"
                    title="Copy"
                  >
                    {copiedKey === apiKey.id ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => deleteKey(apiKey.id)}
                    className="p-1.5 rounded hover:bg-red-500/20 text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Documentation Link */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6 text-center">
        <Key className="w-10 h-10 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)] mb-3">
          Need help with the API? Check out our documentation.
        </p>
        <Button variant="outline" size="sm">
          View API Documentation
        </Button>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-elevated)] p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Create New API Key</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Key Name
                </label>
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g., Production API Key"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button onClick={createNewKey}>
                  Create Key
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
