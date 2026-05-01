import { CostSummary } from '../lib/types';

interface Props {
  summary: CostSummary | null;
}

export default function CostLedger({ summary }: Props) {
  if (!summary) {
    return <div className="border rounded p-4">Loading cost…</div>;
  }
  const overThreshold = summary.total_usd > summary.alert_threshold_usd;
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">MiniMax Cost Ledger</h2>
      <p className={overThreshold ? 'text-red-600 font-bold' : ''}>
        {overThreshold && '⚠ '}
        Today: ${summary.total_usd.toFixed(4)} ({summary.calls} calls)
      </p>
      <p className="text-xs text-gray-500 mt-1">
        Alert threshold: ${summary.alert_threshold_usd.toFixed(2)}/day
      </p>
    </div>
  );
}
