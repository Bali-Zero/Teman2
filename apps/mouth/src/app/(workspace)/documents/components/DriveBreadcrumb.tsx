import { ChevronRight, Home } from 'lucide-react';
import type { BreadcrumbItem } from '@/lib/api/drive/drive.types';
import { Button } from '@/components/ui/button';

interface DriveBreadcrumbProps {
  items: BreadcrumbItem[];
  onNavigate: (index: number) => void;
}

export function DriveBreadcrumb({ items, onNavigate }: DriveBreadcrumbProps) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto whitespace-nowrap pb-2 text-sm text-[var(--foreground-muted)] md:pb-0">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onNavigate(-1)}
        className="h-8 px-2 hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)]"
      >
        <Home className="mr-1 h-4 w-4" />
        Home
      </Button>
      
      {items.map((item, index) => (
        <div key={item.id} className="flex items-center">
          <ChevronRight className="h-4 w-4 text-gray-400" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate(index)}
            className={`h-8 px-2 hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)] ${
              index === items.length - 1
                ? 'font-medium text-[var(--foreground)]'
                : ''
            }`}
          >
            {item.name}
          </Button>
        </div>
      ))}
    </div>
  );
}
