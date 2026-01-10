import { Search, Grid, List, Plus, Upload, Loader2, Cloud, CloudOff } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface DriveToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  onUploadClick: () => void;
  onCreateClick: (e: React.MouseEvent) => void;
  isConnected: boolean;
  isConnecting?: boolean;
  onConnect?: () => void;
}

export function DriveToolbar({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onUploadClick,
  onCreateClick,
  isConnected,
  isConnecting,
  onConnect,
}: DriveToolbarProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-[var(--border)] bg-[var(--background)] p-4 md:flex-row md:items-center md:justify-between">
      {/* Search */}
      <div className="relative flex-1 md:max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--foreground-muted)]" />
        <input
          type="text"
          placeholder="Cerca in Drive..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--background-subtle)] pl-10 pr-4 text-sm focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {!isConnected && onConnect && (
            <Button 
                variant="outline" 
                size="sm" 
                onClick={onConnect} 
                disabled={isConnecting}
                className="text-amber-500 border-amber-500/20 bg-amber-500/10 hover:bg-amber-500/20"
            >
                {isConnecting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CloudOff className="mr-2 h-4 w-4" />}
                Connetti
            </Button>
        )}

        <div className="flex rounded-lg border border-[var(--border)] bg-[var(--background-subtle)] p-1">
          <button
            onClick={() => onViewModeChange('grid')}
            className={`rounded p-1.5 transition-colors ${
              viewMode === 'grid'
                ? 'bg-[var(--background)] text-[var(--foreground)] shadow-sm'
                : 'text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
            }`}
          >
            <Grid className="h-4 w-4" />
          </button>
          <button
            onClick={() => onViewModeChange('list')}
            className={`rounded p-1.5 transition-colors ${
              viewMode === 'list'
                ? 'bg-[var(--background)] text-[var(--foreground)] shadow-sm'
                : 'text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
            }`}
          >
            <List className="h-4 w-4" />
          </button>
        </div>

        <div className="h-6 w-px bg-[var(--border)] mx-1" />

        <Button variant="outline" onClick={onUploadClick}>
          <Upload className="mr-2 h-4 w-4" />
          Carica
        </Button>
        <Button onClick={onCreateClick} className="bg-emerald-600 hover:bg-emerald-700 text-white">
          <Plus className="mr-2 h-4 w-4" />
          Nuovo
        </Button>
      </div>
    </div>
  );
}
