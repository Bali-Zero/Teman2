/**
 * Common Types for Admin Dashboard
 */

// Database types
export interface TableInfo {
  name: string;
  rowCount: number;
  size: string;
}

export interface TableColumn {
  column_name: string;
  data_type: string;
  is_nullable: string;
  column_default: string | null;
}

export interface TableRow {
  [key: string]: unknown;
}

export interface QueryResult {
  rows: TableRow[];
  rowCount: number;
  command: string;
}

// Qdrant types
export interface CollectionInfo {
  name: string;
  vectors_count: number;
  points_count: number;
}

export interface QdrantPoint {
  id: string | number;
  vector?: number[];
  payload?: Record<string, unknown>;
}

// User types
export interface User {
  id: string;
  email: string;
  name?: string;
  created_at?: string;
}

export interface UserDetails {
  facts: UserFact[];
  memories: UserMemory[];
}

export interface UserFact {
  id: string;
  content: string;
  confidence: number;
}

export interface UserMemory {
  id: string;
  content: string;
  timestamp: string;
}

// Knowledge Graph types
export interface KGNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface KGEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

// Calendar types
export interface Calendar {
  id: string;
  name: string;
  color?: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  calendarId: string;
}

// API Response types
export interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
  message?: string;
}

export interface ApiError {
  message: string;
  status?: number;
}

// Utility types
export type LoadingState = "idle" | "loading" | "success" | "error";
