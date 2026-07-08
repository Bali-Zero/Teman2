import { KineticHeading } from "./KineticHeading";

/**
 * RegulatoryDispatch — the one deliberate dark island on the light
 * homepage (Wave 3 "The Dispatch").
 *
 * Spends the WR2 Instagram dark system (antracite #2C2F38 / data-yellow
 * #F4C430 / status-red #C8102E) on-site for the first time — reusing
 * existing brand equity instead of inventing a new treatment. Sits between
 * SocialProof and NewsHero: after the team/trust block, before the news
 * carousel, so the page reads paper → paper → ONE dark editorial beat →
 * paper again (FT "pull quote" rhythm).
 *
 * WR2's Montserrat-uppercase register is approximated with the already-
 * mounted `--font-sans` (Inter) at heavy weight + uppercase + tight
 * tracking — the mandate is additive/no-new-dependencies, and loading a
 * second display font for one section would cost a render-blocking
 * request for a few words of type.
 *
 * Marked `rp-dark-island` so the `.rumah-putih` scoped repaint rules in
 * globals.css (23 guards, all `:not(.rp-dark-island)`) leave this section's
 * hardcoded dark/white colors alone instead of flattening them to paper.
 *
 * Server Component — no interactivity, so the heading's kinetic reveal
 * (KineticHeading) is the only client-boundary cost, same as elsewhere
 * on this page.
 */
export function RegulatoryDispatch() {
  return (
    <section
      className="rp-dark-island py-14 md:py-20 px-5 md:px-10"
      style={{ background: "#2C2F38" }}
    >
      <div className="max-w-[900px] mx-auto text-center">
        <div
          className="text-[10px] font-bold uppercase tracking-[0.28em] mb-6"
          style={{
            color: "#F4C430",
            fontFamily: "var(--font-sans)",
          }}
        >
          Regulatory Watch
        </div>
        <KineticHeading
          as="p"
          className="mb-6"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.01em",
            fontSize: "clamp(22px, 3.4vw, 40px)",
            lineHeight: 1.18,
            color: "#ffffff",
          }}
        >
          Indonesia is mid-way through the{" "}
          <span style={{ color: "#F4C430" }}>KBLI 2025 conversion</span> —
          codes filed under the old system don&apos;t carry over on their
          own.
        </KineticHeading>
        <p
          className="text-[14px] md:text-[15px] max-w-xl mx-auto"
          style={{ color: "rgba(255,255,255,0.68)" }}
        >
          We track every regulatory shift that touches visas, company
          licensing, tax and property — so your filing doesn&apos;t become
          the one that slipped through.
        </p>
      </div>
    </section>
  );
}
