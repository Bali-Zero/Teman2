import PrimeMap3D from '@/components/maps/PrimeMap3D';

export default function PrimePage() {
  return (
    <main className="min-h-screen bg-black p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-4xl font-serif text-white mb-2">Bali Zero Prime</h1>
            <p className="text-slate-400">Advanced 3D Geospatial Intelligence & Zoning Analyzer</p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            v5.2.0-prime | PostGIS Active
          </div>
        </div>
        
        <PrimeMap3D />
        
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-6 bg-slate-900/50 rounded-lg border border-slate-800">
            <h3 className="text-lg font-semibold text-white mb-2">Zoning Verification</h3>
            <p className="text-sm text-slate-400">Instant check for Tourism, Green, and Residential zones in Bali with direct KBLI mapping.</p>
          </div>
          <div className="p-6 bg-slate-900/50 rounded-lg border border-slate-800">
            <h3 className="text-lg font-semibold text-white mb-2">ROI Prediction</h3>
            <p className="text-sm text-slate-400">Historical price data combined with AI-driven growth forecasting for each specific sub-district.</p>
          </div>
          <div className="p-6 bg-slate-900/50 rounded-lg border border-slate-800">
            <h3 className="text-lg font-semibold text-white mb-2">Legal Compliance</h3>
            <p className="text-sm text-slate-400">Integrated with Nuzantara RAG to ensure all business activities (PMA/PMDN) are permitted.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
