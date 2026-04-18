/**
 * Privacy tab — UU PDP surface.
 *
 * Data export and account deletion are processed manually by the team
 * (no self-service endpoints today). Both actions are expressed as
 * pre-filled mailto links so the user can trigger a tracked email
 * without leaving the portal. When self-service data export/delete
 * endpoints ship, swap the mailto anchors for real triggers.
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
        <h3 className="text-sm uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
          Data export
        </h3>
        <p className="text-sm text-[#c9a96e]/70 mb-2">
          Under UU PDP you can request a copy of your personal data at any time.
        </p>
        <a
          href={`mailto:team@balizero.com?subject=${exportSubject}&body=${body}`}
          className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
        >
          Request data export →
        </a>
      </div>
      <div>
        <h3 className="text-sm uppercase tracking-[2px] text-[#c94a4a] mb-2">
          Delete account
        </h3>
        <p className="text-sm text-[#c9a96e]/70 mb-2">
          Account deletion is processed manually. Open a request and our team
          will confirm before removing any data.
        </p>
        <a
          href={`mailto:team@balizero.com?subject=${deleteSubject}&body=${body}`}
          className="text-xs uppercase tracking-[2px] text-[#c94a4a] hover:underline"
        >
          Request account deletion →
        </a>
      </div>
    </section>
  );
}
