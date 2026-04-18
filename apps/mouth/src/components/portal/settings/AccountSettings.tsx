"use client";

import { useMe } from "@/hooks/useMe";

/**
 * Read-only surface of the authenticated user profile.
 *
 * The BE profile endpoint (`/api/auth/profile`) is the source of truth;
 * there is no full edit form at this stage — name/email/role are managed
 * by the admin backoffice. Schema drift from the hook surfaces as an
 * error banner (no silent partial UI).
 */
export function AccountSettings() {
  const { data, error, isLoading } = useMe();

  if (isLoading) {
    return <p className="text-sm text-[#c9a96e]/60">Loading…</p>;
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-[#c94a4a]">
        Unable to load profile.
      </p>
    );
  }

  if (!data) return null;

  return (
    <section className="space-y-4 max-w-md">
      <Field label="Name" value={data.name} />
      <Field label="Email" value={data.email} />
      <Field label="Role" value={data.role} />
      {data.timezone && <Field label="Timezone" value={data.timezone} />}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-1">
        {label}
      </p>
      <p className="text-sm text-[#f0ece4]">{value}</p>
    </div>
  );
}
