export type TimelineScope = "portal" | "workspace";

export type TimelineEntryType =
  | "message"
  | "document"
  | "practice"
  | "deadline"
  | "interaction";

export interface TimelineEntityRef {
  clientId?: number;
  practiceId?: number;
  documentId?: string;
  messageId?: string;
  interactionId?: number;
  practiceCategory?: string;
}

export interface TimelineEntry {
  id: string;
  type: TimelineEntryType;
  occurredAt: string; // ISO 8601
  title: string;
  description?: string;
  status?: string;
  unread?: boolean;
  isFuture?: boolean;
  entity?: TimelineEntityRef;
}

export interface TimelineResponse {
  scope: TimelineScope;
  entries: TimelineEntry[];
  lastUpdated: number;
}
