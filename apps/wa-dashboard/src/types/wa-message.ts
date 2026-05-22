export interface WaMessage {
  id: number;
  direction: "incoming" | "outgoing";
  team_member_phone: string | null;
  counterpart_phone: string | null;
  chat_type: "dm" | "group";
  group_jid: string | null;
  body: string;
  message_date: string | null;
  media_type: string | null;
  attention_priority: number | null;
  client_id: number | null;
  practice_id: number | null;
}

export interface SseStreamState {
  status: "idle" | "connecting" | "open" | "error" | "closed";
  lastEventId: number;
  errorCount: number;
}
