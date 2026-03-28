import Link from 'next/link';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function KBLIBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 text-sm text-[var(--foreground-muted)]"
    >
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="opacity-40">/</span>}
          {item.href ? (
            <Link href={item.href} className="transition-colors hover:text-[var(--kbli-accent)]">
              {item.label}
            </Link>
          ) : (
            <span className="text-[var(--foreground)]" aria-current="page">
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
