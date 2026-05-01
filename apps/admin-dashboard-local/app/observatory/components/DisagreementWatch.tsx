import { AnomalyEntry } from '../lib/types';

interface Props {
  anomalies: AnomalyEntry[];
}

export default function DisagreementWatch({ anomalies }: Props) {
  const disagreements = anomalies.filter((a) => a.label_diff === 'disagree');
  return (
    <div className="border rounded p-4 bg-amber-50">
      <h2 className="font-semibold mb-2">
        Disagreement Watch (LLM ≠ cell self-classifier)
      </h2>
      <p className="text-xs text-gray-600 mb-2">
        Cases where MiniMax labeled anomaly/critical but cell self-classified
        green — the most interesting signal for fase 1+.
      </p>
      {disagreements.length === 0 && (
        <p className="text-gray-400 text-sm">no disagreements yet</p>
      )}
      <ul className="text-sm space-y-1">
        {disagreements.map((a) => (
          <li key={a.outbox_id}>
            <strong>{a.cell_id}</strong>: {a.label} (
            {(a.confidence * 100).toFixed(0)}%) — {a.reasoning}
          </li>
        ))}
      </ul>
    </div>
  );
}
