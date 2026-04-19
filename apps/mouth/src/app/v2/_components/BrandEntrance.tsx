// BrandEntrance — strip between nav and hero carousel.
// Copied verbatim from production homepage ((marketing)/page.tsx lines 744–760).
// The tagline ("Your [3]ali, from Zer[Ω]") and the service subtitle live here.

export function BrandEntrance() {
  return (
    <div className="brand-entrance">
      <div className="brand-inner">
        <div className="brand-text">
          <h2 className="brand-tagline">
            Your
            <img
              className="brand-logo-3-img"
              src="/assets/logo/balizero-3-red-fixed.png?v=1"
              alt="B"
              style={{ height: "1.6em", width: "auto" }}
            />
            ali, from Zer
            <span className="brand-om-circle" />
          </h2>
          <p className="brand-sub">
            Visa · Company · Tax · Property · Intelligence
          </p>
        </div>
      </div>
    </div>
  );
}
