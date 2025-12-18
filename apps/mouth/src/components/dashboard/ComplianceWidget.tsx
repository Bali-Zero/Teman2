import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, AlertTriangle, Bell, Info, ShieldAlert, X } from 'lucide-react';
import { ComplianceAlert } from '@/types/compliance';

interface ComplianceWidgetProps {
  alerts: ComplianceAlert[];
  onDismiss?: (id: string) => void;
}

export const ComplianceWidget: React.FC<ComplianceWidgetProps> = ({ alerts, onDismiss }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  // Filter urgent alerts (warning, urgent, critical)
  const urgentAlerts = alerts.filter(a => ['warning', 'urgent', 'critical'].includes(a.severity));
  const hasAlerts = urgentAlerts.length > 0;

  const getIcon = (severity: string) => {
    switch(severity) {
      case 'critical': return <ShieldAlert className="w-4 h-4 text-red-500" />;
      case 'urgent': return <AlertTriangle className="w-4 h-4 text-orange-500" />;
      case 'warning': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default: return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  const getColor = (severity: string) => {
    switch(severity) {
      case 'critical': return 'bg-red-500/10 border-red-500/20 text-red-200';
      case 'urgent': return 'bg-orange-500/10 border-orange-500/20 text-orange-200';
      case 'warning': return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-200';
      default: return 'bg-blue-500/10 border-blue-500/20 text-blue-200';
    }
  };

  if (!hasAlerts) return null;

  return (
    <div className="relative">
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-full hover:bg-white/10 transition-colors"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        <Bell className="w-5 h-5 text-white/70" />
        <span className="absolute top-1 right-1 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-black animate-pulse" />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10, x: -100 }}
            animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="absolute right-0 top-12 w-64 z-50 rounded-xl bg-black/80 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden"
          >
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Compliance Alerts</h3>
              <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full font-medium">
                {urgentAlerts.length} Action Items
              </span>
            </div>

            <div className="max-h-[300px] overflow-y-auto p-2 space-y-2">
              {urgentAlerts.map((alert) => (
                <div 
                  key={alert.alert_id}
                  className={`p-3 rounded-lg border flex flex-col gap-2 ${getColor(alert.severity)}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 font-medium text-xs uppercase tracking-wide">
                      {getIcon(alert.severity)}
                      {alert.severity}
                    </div>
                    {onDismiss && (
                      <button 
                        onClick={(e) => { e.stopPropagation(); onDismiss(alert.alert_id); }}
                        className="text-white/20 hover:text-white/50"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>

                  <div>
                    <h4 className="font-semibold text-sm mb-1 line-clamp-1">{alert.title.replace(/^(CRITICAL|URGENT|WARNING|INFO): /, '')}</h4>
                    <p className="text-xs opacity-80 leading-relaxed mb-2">
                      {alert.message}
                    </p>
                    <div className="flex items-center gap-2 pt-2 border-t border-white/5">
                       <span className="text-[10px] font-mono opacity-60">Due: {new Date(alert.deadline).toLocaleDateString()}</span>
                       <span className="text-[10px] font-mono opacity-60 ml-auto">{alert.days_until_deadline} days left</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 border-t border-white/10 bg-white/5 text-center">
              <button className="text-xs text-emerald-400 hover:text-emerald-300 font-medium tracking-wide">
                VIEW COMPLIANCE DASHBOARD
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
