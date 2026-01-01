import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Zantara Client Portal',
  description: 'Manage your visa, company, and tax services with Bali Zero',
};

export default function PortalGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
