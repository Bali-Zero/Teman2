import type { Metadata } from "next";
import "./oracle.css";

// Route-local pre-paint bootstrap. The root layout uses the same raw-script
// pattern because App Router's beforeInteractive scripts can land too late to
// prevent a first-frame theme flash. This only writes an oracle-namespaced
// hint; it never changes the site's global data-theme.
const oracleThemeInitScript = `(function(){var t='light';try{var s=localStorage.getItem('visa-oracle-theme');if(s==='light'||s==='dark'){t=s;}else if(typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches){t='dark';}}catch(e){try{if(typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches){t='dark';}}catch(_){}}document.documentElement.setAttribute('data-oracle-theme-bootstrap',t);})();`;

export const metadata: Metadata = {
  title: "Visa Oracle",
  description:
    "Bilingual decision support for Indonesian visa pathways, backed by deterministic evaluation and dated sources.",
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
