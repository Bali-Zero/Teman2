export const OWNER_EMAILS = new Set([
  "zero@balizero.com",
  "antonellosiano@balizero.com",
]);

export function isOwner(email: string | null | undefined): boolean {
  return !!email && OWNER_EMAILS.has(email);
}
