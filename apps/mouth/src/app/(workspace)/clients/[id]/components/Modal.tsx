'use client';

import React, { useEffect } from 'react';
import { X, Save, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Modal({
  title,
  onClose,
  children,
  isSaving,
  onSave,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  isSaving: boolean;
  onSave: (e: React.FormEvent) => void;
}) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSaving) onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose, isSaving]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[var(--bz-base)] border border-[var(--bz-border)] rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-[var(--bz-border)]">
          <h2 className="text-xl font-semibold text-[var(--bz-text-1)]">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close modal">
            <X className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={onSave} className="overflow-y-auto flex-1">
          <div className="p-6 space-y-6">{children}</div>
          <div className="flex items-center justify-end gap-3 p-6 border-t border-[var(--bz-border)] bg-[var(--bz-surface)] mt-auto">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving} className="gap-2">
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
