/**
 * Privacy tab — UU PDP surface.
 *
 * Data export and account deletion are processed manually by the team
 * (no self-service endpoints today). Both actions are expressed as
 * pre-filled mailto links so the user can trigger a tracked email
 * without leaving the portal. When self-service data export/delete
 * endpoints ship, swap the mailto anchors for real triggers. *
 * WS3 slice 7 (GARUDA Day Edition): headings/body --bz-text-2, export
 * link --bz-copper-text (slice-1 fallback), deletion --state-danger
 * (was #c9a96e/#d4845a/#c94a4a).
 */
export function PrivacySettings() {
  const exportSubject = encodeURIComponent("Data export request");
  const deleteSubject = encodeURIComponent("Account deletion request");
  const body = encodeURIComponent(
    "Hi team,\n\nI'd like to request this action for my Bali Zero client account.\n\nRegistered email: ",
  );

  return (
    <section className="space-y-6 max-w-lg">
      <div>
        <h3 className="text-sm uppercase tracking-[2px] text-[var(--bz-text-2)] mb-2">
          Data export
        </h3>
        <p className="text-sm text-[var(--bz-text-2)] mb-2">
          Under UU PDP you can request a copy of your personal data at any time.
        </p>
        <a
          href={`mailto:team@balizero.com?subject=${exportSubject}&body=${body}`}
          className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] hover:underline"
        >
          Request data export →
        </a>
      </div>
      <div>
        <h3 className="text-sm uppercase tracking-[2px] text-[var(--state-danger)] mb-2">
          Delete account
        </h3>
        <p className="text-sm text-[var(--bz-text-2)] mb-2">
          Account deletion is processed manually. Open a request and our team
          will confirm before removing any data.
        </p>
        <a
          href={`mailto:team@balizero.com?subject=${deleteSubject}&body=${body}`}
          className="text-xs uppercase tracking-[2px] text-[var(--state-danger)] hover:underline"
        >
          Request account deletion →
        </a>
      </div>
    </section>
  );
}
