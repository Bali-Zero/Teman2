interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface Props {
  items?: BreadcrumbItem[];
}

export function KBLIBreadcrumb({ items }: Props) {
  return <div>Breadcrumb</div>;
}
