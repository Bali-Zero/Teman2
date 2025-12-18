import Link from 'next/link';
import { buttonVariants } from '@/components/ui/button';
import { FileQuestion } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-[var(--background)] text-[var(--foreground)] gap-6">
      <div className="flex items-center justify-center w-24 h-24 rounded-full bg-[var(--background-secondary)]">
        <FileQuestion className="w-12 h-12 text-[var(--foreground-muted)]" />
      </div>

      <div className="text-center space-y-2 max-w-md px-4">
        <h1 className="text-3xl font-bold tracking-tight">Page Not Found</h1>
        <p className="text-[var(--foreground-secondary)]">
          The page you are looking for does not exist or has been moved.
        </p>
      </div>

      <div className="flex gap-4">
        <Link href="/" className={buttonVariants({ variant: 'default' })}>
          Return Home
        </Link>
        <Link href="/chat" className={buttonVariants({ variant: 'outline' })}>
          Go to Chat
        </Link>
      </div>
    </div>
  );
}
