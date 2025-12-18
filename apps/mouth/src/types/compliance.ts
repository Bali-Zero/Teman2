export type AlertSeverity = 'info' | 'warning' | 'urgent' | 'critical';
export type AlertStatus = 'pending' | 'sent' | 'acknowledged' | 'resolved' | 'expired';
export type ComplianceType = 'visa_expiry' | 'tax_filing' | 'license_renewal' | 'permit_renewal' | 'regulatory_change' | 'document_expiry';

export interface ComplianceAlert {
  alert_id: string;
  compliance_item_id: string;
  client_id: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  deadline: string;
  days_until_deadline: number;
  action_required: string;
  estimated_cost?: number;
  status: AlertStatus;
  created_at: string;
}
