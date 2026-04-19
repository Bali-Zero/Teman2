import AnomalyBanner from "@/components/AnomalyBanner";
import CostKpiCards from "@/components/CostKpiCards";
import CostTimeline from "@/components/CostTimeline";
import ModelMix from "@/components/ModelMix";
import RecommendationPanel from "@/components/RecommendationPanel";
import TopEndpoints from "@/components/TopEndpoints";

export const dynamic = "force-dynamic";

export default function CostDashboard() {
  return (
    <main className="min-h-screen space-y-6 bg-slate-950 p-6 text-slate-100">
      <header>
        <h1 className="text-2xl font-bold">LLM Cost Dashboard</h1>
        <p className="text-sm text-slate-400">
          Pro local — port 3100. Not deployed. Source: PR #123 / migration 119.
        </p>
      </header>

      <AnomalyBanner />
      <CostKpiCards />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CostTimeline />
        <ModelMix />
      </div>

      <TopEndpoints />
      <RecommendationPanel />
    </main>
  );
}
