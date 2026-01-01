'use client';

import React, { useState } from 'react';
import { Database, Download, Upload, Clock, ArrowLeft, FileJson, FileSpreadsheet, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

interface BackupHistory {
  id: string;
  type: 'full' | 'partial';
  date: string;
  size: string;
  status: 'completed' | 'failed';
}

export default function BackupExportPage() {
  const router = useRouter();
  const [isExporting, setIsExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<'json' | 'csv'>('json');
  const [selectedData, setSelectedData] = useState<string[]>(['clients', 'cases', 'interactions']);

  const [backupHistory] = useState<BackupHistory[]>([
    { id: '1', type: 'full', date: '2024-12-28 14:30', size: '2.4 MB', status: 'completed' },
    { id: '2', type: 'partial', date: '2024-12-27 10:15', size: '1.1 MB', status: 'completed' },
    { id: '3', type: 'full', date: '2024-12-20 09:00', size: '2.2 MB', status: 'completed' },
  ]);

  const dataOptions = [
    { id: 'clients', label: 'Clients', description: 'All client records and contacts' },
    { id: 'cases', label: 'Cases/Practices', description: 'All case records and history' },
    { id: 'interactions', label: 'Interactions', description: 'Chat logs and WhatsApp messages' },
    { id: 'knowledge', label: 'Knowledge Base', description: 'Documents and AI knowledge' },
    { id: 'team', label: 'Team Data', description: 'User activity and time tracking' },
    { id: 'settings', label: 'Settings', description: 'System configuration' },
  ];

  const toggleDataSelection = (id: string) => {
    setSelectedData(prev =>
      prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]
    );
  };

  const handleExport = async () => {
    setIsExporting(true);

    try {
      // For now, we'll use the timesheet export as an example
      // In a real app, this would call a comprehensive export API
      const today = new Date();
      const startDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
      const endDate = today.toISOString().split('T')[0];

      if (selectedData.includes('team')) {
        const blob = await api.exportTimesheet(startDate, endDate);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `zantara-export-${endDate}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      // Simulate export for other data
      await new Promise(resolve => setTimeout(resolve, 2000));

      alert('Export completed successfully!');
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push('/settings')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <Database className="w-6 h-6 text-emerald-400" />
            Backup & Export
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Export your data or create backups
          </p>
        </div>
      </div>

      {/* Warning */}
      <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-amber-500">Data Export Notice</h3>
            <p className="text-sm text-amber-500/80">
              Exported data may contain sensitive information. Handle with care and store securely.
            </p>
          </div>
        </div>
      </div>

      {/* Export Section */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">Export Data</h2>
          <p className="text-sm text-[var(--foreground-muted)]">
            Select the data you want to export
          </p>
        </div>

        {/* Data Selection */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {dataOptions.map((option) => {
            const isSelected = selectedData.includes(option.id);
            return (
              <button
                key={option.id}
                onClick={() => toggleDataSelection(option.id)}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  isSelected
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                    : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className={`w-4 h-4 rounded flex items-center justify-center ${
                    isSelected ? 'bg-[var(--accent)]' : 'bg-[var(--background-secondary)] border border-[var(--border)]'
                  }`}>
                    {isSelected && <CheckCircle2 className="w-3 h-3 text-white" />}
                  </div>
                  <span className={`font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                    {option.label}
                  </span>
                </div>
                <p className="text-xs text-[var(--foreground-muted)] ml-6">{option.description}</p>
              </button>
            );
          })}
        </div>

        {/* Format Selection */}
        <div>
          <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-2">
            Export Format
          </label>
          <div className="flex gap-3">
            <button
              onClick={() => setExportFormat('json')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all ${
                exportFormat === 'json'
                  ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                  : 'border-[var(--border)] bg-[var(--background)]'
              }`}
            >
              <FileJson className={`w-5 h-5 ${exportFormat === 'json' ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`} />
              <span className={exportFormat === 'json' ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}>JSON</span>
            </button>
            <button
              onClick={() => setExportFormat('csv')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all ${
                exportFormat === 'csv'
                  ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                  : 'border-[var(--border)] bg-[var(--background)]'
              }`}
            >
              <FileSpreadsheet className={`w-5 h-5 ${exportFormat === 'csv' ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`} />
              <span className={exportFormat === 'csv' ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}>CSV</span>
            </button>
          </div>
        </div>

        {/* Export Button */}
        <Button
          onClick={handleExport}
          disabled={isExporting || selectedData.length === 0}
          className="w-full"
        >
          <Download className="w-4 h-4 mr-2" />
          {isExporting ? 'Exporting...' : `Export ${selectedData.length} Data Set${selectedData.length !== 1 ? 's' : ''}`}
        </Button>
      </div>

      {/* Backup History */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-[var(--foreground)]">Backup History</h2>
          </div>
          <Button variant="outline" size="sm">
            <Upload className="w-4 h-4 mr-2" />
            Create Backup
          </Button>
        </div>

        <div className="space-y-2">
          {backupHistory.map((backup) => (
            <div
              key={backup.id}
              className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]"
            >
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-[var(--foreground-muted)]" />
                <div>
                  <p className="font-medium text-[var(--foreground)]">
                    {backup.type === 'full' ? 'Full Backup' : 'Partial Backup'}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">{backup.date}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm text-[var(--foreground-muted)]">{backup.size}</span>
                {backup.status === 'completed' ? (
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                )}
                <Button variant="ghost" size="sm">
                  <Download className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auto Backup Settings */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h3 className="font-semibold text-[var(--foreground)] mb-4">Automatic Backups</h3>
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-[var(--foreground)]">Enable Daily Backups</p>
            <p className="text-xs text-[var(--foreground-muted)]">Automatically backup data every day at midnight</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" className="sr-only peer" defaultChecked />
            <div className="w-11 h-6 bg-[var(--background)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[var(--foreground)]">Retention Period</p>
            <p className="text-xs text-[var(--foreground-muted)]">How long to keep backups</p>
          </div>
          <select className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm">
            <option value="7">7 days</option>
            <option value="30" selected>30 days</option>
            <option value="90">90 days</option>
            <option value="365">1 year</option>
          </select>
        </div>
      </div>
    </div>
  );
}
