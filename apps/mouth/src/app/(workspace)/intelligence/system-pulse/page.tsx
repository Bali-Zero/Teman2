export default function SystemPulsePage() {
  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div className="p-6 bg-white dark:bg-slate-950 rounded-lg border shadow-sm">
        <h3 className="text-sm font-medium text-slate-500 mb-2">Qdrant Status</h3>
        <div className="text-2xl font-bold text-green-500">Healthy</div>
        <p className="text-xs text-slate-400 mt-1">54,154 vectors indexed</p>
      </div>
      
      <div className="p-6 bg-white dark:bg-slate-950 rounded-lg border shadow-sm">
        <h3 className="text-sm font-medium text-slate-500 mb-2">Agent Status</h3>
        <div className="text-2xl font-bold text-green-500">Active</div>
        <p className="text-xs text-slate-400 mt-1">Last run: 5 mins ago</p>
      </div>

      <div className="p-6 bg-white dark:bg-slate-950 rounded-lg border shadow-sm">
        <h3 className="text-sm font-medium text-slate-500 mb-2">API Usage (Today)</h3>
        <div className="text-2xl font-bold">12,450</div>
        <p className="text-xs text-slate-400 mt-1">Tokens consumed</p>
      </div>
    </div>
  );
}
