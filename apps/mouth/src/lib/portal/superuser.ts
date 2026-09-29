export type PortalSuperuser = {
  isSuperuser: boolean;
  email: string | null;
};

// The authenticated layout awaits this before rendering anything, so a hung
// probe must not pin the shell on its spinner: past this it reads as "no".
export const PORTAL_SUPERUSER_PROBE_TIMEOUT_MS = 5_000;

const notSuperuser: PortalSuperuser = { isSuperuser: false, email: null };

export async function fetchPortalSuperuser(
  token?: string | null,
): Promise<PortalSuperuser> {
  try {
    const response = await fetch("/api/portal/admin/me", {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: AbortSignal.timeout(PORTAL_SUPERUSER_PROBE_TIMEOUT_MS),
    });

    if (!response.ok) return notSuperuser;

    const data = (await response.json()) as {
      is_superuser?: unknown;
      email?: unknown;
    };
    if (typeof data.is_superuser !== "boolean") return notSuperuser;

    return {
      isSuperuser: data.is_superuser,
      email: typeof data.email === "string" ? data.email : null,
    };
  } catch {
    return notSuperuser;
  }
}
