import { DailyRollup } from '../lib/types';

interface Props {
  rollups: DailyRollup[];
}

export default function CellBreakdown({ rollups }: Props) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Per-Cell Breakdown (today)</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b">
            <th className="pb-1">Cell</th>
            <th className="pb-1 text-center">Pulses</th>
            <th className="pb-1 text-center">Anomaly%</th>
            <th className="pb-1 text-center">Disagree%</th>
          </tr>
        </thead>
        <tbody>
          {rollups.length === 0 && (
            <tr>
              <td colSpan={4} className="text-gray-400 text-center py-2">
                no data yet
              </td>
            </tr>
          )}
          {rollups.map((r) => (
            <tr key={r.cell_id} className="border-b last:border-0">
              <td className="py-1">{r.cell_id}</td>
              <td className="py-1 text-center">{r.n_pulse}</td>
              <td className="py-1 text-center">
                {r.n_pulse > 0 ? ((r.n_anomaly / r.n_pulse) * 100).toFixed(1) : '0.0'}%
              </td>
              <td className="py-1 text-center">
                {r.n_pulse > 0 ? ((r.n_disagree / r.n_pulse) * 100).toFixed(1) : '0.0'}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
