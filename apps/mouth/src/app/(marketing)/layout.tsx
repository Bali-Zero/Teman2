/**
 * Marketing layout — balizero.com homepage
 * No shared header/footer: the draft has its own navbar and footer embedded.
 * Only adds the <html> and <body> wrappers from the root layout.
 */
export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
