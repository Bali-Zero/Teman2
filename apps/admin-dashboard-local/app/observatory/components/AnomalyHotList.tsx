import { AnomalyEntry } from '../lib/types';

interface Props {
  anomalies: AnomalyEntry[];
}

export default function AnomalyHotList({ anomalies }: Props) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Anomaly Hot List</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b">
            <th className="pb-1">Time</th>
            <th className="pb-1">Cell</th>
            <th className="pb-1">Label</th>
            <th className="pb-1 text-center">Confidence</th>
            <th className="pb-1">Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {anomalies.length === 0 && (
            <tr>
              <td colSpan={5} className="text-gray-400 text-center py-2">
                no anomalies in window
              </td>
            </tr>
          )}
          {anomalies.map((a) => (
            <tr key={a.outbox_id} className="border-b last:border-0">
              <td className="py-1 text-xs">
                {new Date(a.pulse_timestamp).toLocaleTimeString()}
              </td>
              <td className="py-1">{a.cell_id}</td>
              <td className="py-1">
                <span
                  className={
                    a.label === 'critical'
                      ? 'text-red-600 font-bold'
                      : a.label === 'anomaly'
                      ? 'text-yellow-600'
                      : 'text-gray-500'
                  }
                >
                  {a.label}
                </span>
              </td>
              <td className="py-1 text-center">
                {(a.confidence * 100).toFixed(0)}%
              </td>
              <td className="py-1 text-xs text-gray-600 truncate max-w-md">
                {a.reasoning}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
