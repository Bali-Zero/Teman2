import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getCode, getAllCodes } from "@/lib/kbli-data.server";
import { KBLICodeJsonLd, KBLIBreadcrumbJsonLd } from "@/components/kbli/KBLIStructuredData";
import Link from "next/link";
import { Activity } from "lucide-react";

// SSG: Generate all 1,563 pages at build time
export async function generateStaticParams() {
  const codes = getAllCodes();
  return codes.map((c) => ({ code: c.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: codeParam } = await params;
  const codeData = getCode(codeParam);
  if (!codeData) return { title: "KBLI Code Not Found" };

  const title = `KBLI ${codeData.code}: ${codeData.titleId} — Business Guide | Bali Zero`;
  const description = `Complete guide for KBLI ${codeData.code} (${codeData.titleId}). Check foreign ownership (PMA) status, license requirements, and risk level for this Indonesian business activity.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      url: `https://balizero.com/kbli/${codeData.code}`,
    },
    alternates: {
      canonical: `https://balizero.com/kbli/${codeData.code}`,
    },
  };
}

export default async function KBLICodePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code: codeParam } = await params;
  const codeData = getCode(codeParam);

  if (!codeData) {
    notFound();
  }

  return (
    <>
      <KBLICodeJsonLd code={codeData} />
      <KBLIBreadcrumbJsonLd 
        items={[
          { name: "KBLI Navigator", url: "https://balizero.com/kbli" },
          { name: `Section ${codeData.section}`, url: "https://balizero.com/kbli" },
          { name: codeData.code, url: `https://balizero.com/kbli/${codeData.code}` }
        ]} 
      />
      <div className="max-w-4xl mx-auto px-4 py-12">
      <nav className="mb-8">
        <Link href="/kbli" className="text-amber-600 hover:underline">
          ← Back to KBLI Navigator
        </Link>
      </nav>

      <header className="mb-12">
        <div className="flex items-center gap-4 mb-4">
          <span className="bg-amber-100 text-amber-800 px-3 py-1 rounded-full font-mono font-bold text-lg border border-amber-200">
            KBLI {codeData.code}
          </span>
          <span className={`px-3 py-1 rounded-full text-sm font-medium uppercase border ${
            codeData.pma.status === 'open' ? 'bg-green-50 text-green-700 border-green-200' :
            codeData.pma.status === 'restricted' ? 'bg-yellow-50 text-amber-700 border-yellow-200' :
            'bg-red-50 text-red-700 border-red-200'
          }`}>
            PMA: {codeData.pma.status}
          </span>
        </div>
        <h1 className="text-4xl font-bold text-slate-900 mb-2 leading-tight">
          {codeData.titleId}
        </h1>
        <p className="text-xl text-slate-500 italic">
          {codeData.titleEn}
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2 space-y-10">
          <section>
            <h2 className="text-2xl font-semibold text-slate-800 mb-4">Description</h2>
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm leading-relaxed text-slate-700 whitespace-pre-line">
              {codeData.description}
            </div>
          </section>

          {/* NEW: 2026 Business Intelligence Section */}
          {codeData.intel && (
            <section className="space-y-6">
              <h2 className="text-2xl font-semibold text-slate-800 flex items-center gap-2">
                <span className="p-1.5 bg-blue-100 rounded-lg text-blue-600">
                  <Activity className="w-5 h-5" />
                </span>
                2026 Business Intelligence
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-5">
                  <h3 className="text-blue-900 font-bold text-sm uppercase tracking-wider mb-2">Market Sentiment</h3>
                  <p className="text-slate-700 text-sm leading-relaxed">{codeData.intel.market_sentiment}</p>
                </div>
                <div className="bg-amber-50/50 border border-amber-100 rounded-xl p-5">
                  <h3 className="text-amber-900 font-bold text-sm uppercase tracking-wider mb-2">The Bali Nuance</h3>
                  <p className="text-slate-700 text-sm leading-relaxed">{codeData.intel.bali_nuance}</p>
                </div>
                <div className="bg-green-50/50 border border-green-100 rounded-xl p-5">
                  <h3 className="text-green-900 font-bold text-sm uppercase tracking-wider mb-2">Strategic ROI</h3>
                  <p className="text-slate-700 text-sm leading-relaxed">{codeData.intel.investment_outlook}</p>
                </div>
                <div className="bg-red-50/50 border border-red-100 rounded-xl p-5">
                  <h3 className="text-red-900 font-bold text-sm uppercase tracking-wider mb-2">Operational Hurdles</h3>
                  <p className="text-slate-700 text-sm leading-relaxed">{codeData.intel.operational_risks}</p>
                </div>
              </div>

              <div className="bg-slate-100 border border-slate-200 rounded-xl p-4 text-xs text-slate-500 italic">
                <strong>Legacy Bridge:</strong> {codeData.intel.legacy_bridge}
              </div>
            </section>
          )}

          <section>
            <h2 className="text-2xl font-semibold text-slate-800 mb-4">Licensing by Business Scale</h2>
            <div className="space-y-4">
              {codeData.licensing.map((lic, idx) => (
                <div key={idx} className="border border-slate-200 rounded-lg p-5 bg-slate-50">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="font-bold text-slate-800">{lic.scales.join(", ")}</h3>
                    <span className="text-xs font-bold uppercase tracking-wider bg-slate-200 px-2 py-1 rounded">
                      Risk: {lic.riskCategory}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                    <div>
                      <p className="text-slate-500 mb-1 uppercase text-[10px] font-bold tracking-widest">License Type</p>
                      <p className="font-medium text-slate-800">{lic.licenseType}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 mb-1 uppercase text-[10px] font-bold tracking-widest">Timeline</p>
                      <p className="font-medium text-slate-800">{lic.timeline}</p>
                    </div>
                  </div>
                  {lic.requirements.length > 0 && (
                    <div className="mt-4">
                      <p className="text-slate-500 mb-2 uppercase text-[10px] font-bold tracking-widest">Requirements</p>
                      <ul className="list-disc list-inside space-y-1 text-slate-600">
                        {lic.requirements.map((req, ridx) => (
                          <li key={ridx}>{req}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-8">
          <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-xl relative overflow-hidden">
            <div className="relative z-10">
              <h3 className="text-lg font-bold mb-2 flex items-center gap-2">
                <span className="text-amber-400">✨</span> Ask Zantara AI
              </h3>
              <p className="text-slate-400 text-sm mb-4">
                Get practical advice on how to use KBLI {codeData.code} for your Bali project.
              </p>
              <div className="bg-white/10 rounded-lg p-3 text-xs border border-white/10 italic text-slate-300">
                "What permits do I need for a restaurant in Canggu under this code?"
              </div>
              <button className="w-full mt-4 bg-amber-500 hover:bg-amber-400 text-slate-900 font-bold py-2 rounded-lg transition-colors text-sm">
                Open Expert Chat
              </button>
            </div>
            {/* Background glow */}
            <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-amber-500/20 blur-3xl rounded-full"></div>
          </div>

          <div className="bg-amber-50 border border-amber-100 rounded-xl p-6">
            <h3 className="font-bold text-amber-900 mb-3">Investment Summary</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-amber-200/50 pb-2">
                <span className="text-amber-800/70">Foreign Ownership</span>
                <span className="font-bold text-amber-900">{codeData.pma.maxForeign}%</span>
              </div>
              <div className="flex justify-between border-b border-amber-200/50 pb-2">
                <span className="text-amber-800/70">Min. Capital</span>
                <span className="font-bold text-amber-900">Rp 10 Billion</span>
              </div>
              <div className="flex justify-between">
                <span className="text-amber-800/70">Section</span>
                <span className="font-bold text-amber-900">{codeData.sectionName}</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
    </>
  );
}
