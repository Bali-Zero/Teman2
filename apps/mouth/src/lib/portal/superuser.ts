type PortalSuperuser = {
  isSuperuser: boolean;
  email: string | null;
};

const notSuperuser: PortalSuperuser = { isSuperuser: false, email: null };

export async function fetchPortalSuperuser(
  token?: string | null,
): Promise<PortalSuperuser> {
  try {
    const response = await fetch("/api/portal/admin/me", {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
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
