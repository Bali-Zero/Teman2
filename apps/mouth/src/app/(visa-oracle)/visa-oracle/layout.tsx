import type { Metadata } from "next";
import "./oracle.css";

// Route-local pre-paint bootstrap. The root layout uses the same raw-script
// pattern because App Router's beforeInteractive scripts can land too late to
// prevent a first-frame theme flash. This only writes an oracle-namespaced
// hint; it never changes the site's global data-theme.
const oracleThemeInitScript = `(function(){var t='light';try{var s=localStorage.getItem('visa-oracle-theme');if(s==='light'||s==='dark'){t=s;}else if(typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches){t='dark';}}catch(e){try{if(typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches){t='dark';}}catch(_){}}document.documentElement.setAttribute('data-oracle-theme-bootstrap',t);})();`;

// Restored 2026-08-23 (Zero, Legge 5): the engine runs in SHADOW — its
// verdicts are not authoritative — and DPIA §8 is unsigned. Removed
// accidentally by the metadata rewrite in #3732 (2026-08-07), where no
// test caught the drop. Ratification is a future Zero decision, not this
// comment's to make: it requires DPIA §8 signed, seq-13 active with its
// two doctrine gaps cured, a SHADOW→ENFORCE decision (or accuracy gate
// passed), and E30 prices defined. Do not drop this without that ruling —
// layout.test.tsx pins it so a future rewrite fails loud, not silent.
export const metadata: Metadata = {
  title: "Visa Oracle",
  description:
    "Bilingual decision support for Indonesian visa pathways, backed by deterministic evaluation and dated sources.",
  robots: { index: false, follow: false },
};

export default function VisaOracleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: oracleThemeInitScript }} />
      {children}
    </>
  );
}
