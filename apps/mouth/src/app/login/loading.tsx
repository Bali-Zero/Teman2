/**
 * The /login skeleton, on concept-K "SIAP".
 *
 * It used to be a generic centred card — a 64px circle and three 44px rounded
 * rows — which is the shape of a profile page, not of this one. A skeleton that
 * does not predict the layout makes the real page JUMP when it arrives. This
 * one is the login's own silhouette: the forest band, then the copper rule, the
 * headline, two 52px fields and the button, at the same widths.
 *
 * No Skeleton component: its pulse is a shadcn grey. The wash token is the
 * alphabet's own quiet surface, and it is still and legible on paper.
 */
export default function LoginLoading() {
  return (
    <div
      aria-hidden="true"
      className="flex min-h-screen w-full flex-col bg-[var(--bz-base)] lg:flex-row"
    >
      <div
        className="h-[120px] w-full shrink-0 lg:h-auto lg:min-h-screen lg:w-[40%]"
        style={{ background: "var(--bz-panel)" }}
      />
      <div className="flex w-full flex-1 items-center justify-center px-6 py-12 lg:w-[60%] lg:px-16">
        <div className="w-full max-w-[380px]">
          <div className="mb-5 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]" />
          <div className="h-[30px] w-[220px] bg-[var(--bz-wash)]" />
          <div className="mt-3 h-[13px] w-[260px] bg-[var(--bz-wash)]" />
          <div className="mt-7 flex flex-col gap-6">
            <div className="h-[52px] w-full border-b border-[var(--line-control)]" />
            <div className="h-[52px] w-full border-b border-[var(--line-control)]" />
            <div className="mt-1 h-12 w-full bg-[var(--bz-wash)]" />
          </div>
        </div>
      </div>
    </div>
  );
}
