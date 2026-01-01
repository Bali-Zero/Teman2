/**
 * Portal API Types
 * Types for the client-facing portal
 */

// ============================================================================
// Dashboard Types
// ============================================================================

export interface PortalDashboard {
  visa: {
    status: 'active' | 'pending' | 'warning' | 'expired' | 'none';
    type: string | null;
    expiryDate: string | null;
    daysRemaining: number | null;
  };
  company: {
    status: 'active' | 'pending' | 'none';
    primaryCompanyName: string | null;
    totalCompanies: number;
  };
  taxes: {
    status: 'compliant' | 'attention' | 'overdue';
    nextDeadline: string | null;
    daysToDeadline: number | null;
  };
  documents: {
    total: number;
    pending: number;
  };
  messages: {
    unread: number;
  };
  actions: PortalAction[];
}

export interface PortalAction {
  id: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  type: string;
  href: string;
}

// ============================================================================
// Visa Types
// ============================================================================

export interface VisaInfo {
  current: {
    type: string;
    status: 'active' | 'pending' | 'expired';
    issueDate: string;
    expiryDate: string;
    daysRemaining: number;
    permitNumber: string;
    sponsor: string;
  } | null;
  history: VisaHistoryItem[];
  documents: PortalDocument[];
}

export interface VisaHistoryItem {
  id: string;
  type: string;
  period: string;
  status: 'completed' | 'expired';
}

// ============================================================================
// Company Types
// ============================================================================

export interface PortalCompany {
  id: number;
  name: string;
  type: string;
  status: 'active' | 'pending';
  isPrimary: boolean;
  address: string;
  directors: string[];
  licenses: CompanyLicense[];
  compliance: ComplianceItem[];
}

export interface CompanyLicense {
  id: string;
  name: string;
  status: 'active' | 'expiring' | 'expired';
  expiryDate: string;
  daysRemaining?: number;
}

export interface ComplianceItem {
  id: string;
  name: string;
  dueDate: string;
  status: 'upcoming' | 'overdue' | 'completed';
}

// ============================================================================
// Tax Types
// ============================================================================

export interface TaxOverview {
  summary: {
    status: 'compliant' | 'attention' | 'overdue';
    totalDue: number;
    nextDeadline: string | null;
    daysToDeadline: number | null;
  };
  obligations: TaxObligation[];
  history: TaxHistoryItem[];
}

export interface TaxObligation {
  id: string;
  name: string;
  type: string;
  period: string;
  dueDate: string;
  status: 'pending' | 'filed' | 'overdue';
  amount?: number;
}

export interface TaxHistoryItem {
  id: string;
  name: string;
  period: string;
  filedDate: string;
  amount: number;
}

// ============================================================================
// Document Types
// ============================================================================

export interface PortalDocument {
  id: string;
  name: string;
  type: string;
  category: string;
  status: 'verified' | 'pending' | 'expired';
  uploadDate: string;
  expiryDate?: string;
  size: string;
  downloadUrl?: string;
}

// ============================================================================
// Message Types
// ============================================================================

export interface PortalMessage {
  id: string;
  content: string;
  direction: 'client_to_team' | 'team_to_client';
  sentBy: string;
  subject?: string;
  practiceId?: number;
  createdAt: string;
  readAt?: string;
}

export interface MessagesResponse {
  messages: PortalMessage[];
  total: number;
  unreadCount: number;
}

export interface SendMessageRequest {
  content: string;
  subject?: string;
  practiceId?: number;
}

// ============================================================================
// Settings Types
// ============================================================================

export interface PortalPreferences {
  emailNotifications: boolean;
  whatsappNotifications: boolean;
  language: string;
  timezone: string;
}

export interface PortalProfile {
  id: number;
  fullName: string;
  email: string;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  passportNumber?: string;
  address?: string;
  memberSince: string;
}

// ============================================================================
// Invitation Types
// ============================================================================

export interface InviteValidationResponse {
  valid: boolean;
  error?: string;
  message?: string;
  clientName?: string;
  email?: string;
  invitationId?: number;
  clientId?: number;
}

export interface CompleteRegistrationRequest {
  token: string;
  pin: string;
}

export interface RegistrationResponse {
  success: boolean;
  message: string;
  userId?: string;  // UUID string from team_members
  redirectTo?: string;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface PortalApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}
