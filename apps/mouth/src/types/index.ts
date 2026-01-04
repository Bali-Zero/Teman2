export interface Source {
  id?: number;
  title?: string;
  content?: string;
  snippet?: string;
  url?: string;
  score?: number;
  collection?: string;
  doc_id?: string;
  download_url?: string | null;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  team?: string;
  status?: string;
  avatar?: string;
  metadata?: Record<string, unknown> | null;
  language_preference?: string;
}

export type AgentStep =
  | { type: 'status'; data: string; timestamp: Date }
  | { type: 'thinking'; data: string; timestamp: Date }
  | { type: 'tool_call'; data: { tool: string; args: Record<string, unknown> }; timestamp: Date }
  | { type: 'tool_start'; data: { name: string; args: Record<string, unknown> }; timestamp: Date }
  | { type: 'tool_end'; data: { result: string }; timestamp: Date }
  | { type: 'observation'; data: string; timestamp: Date }
  | { type: 'phase'; data: { name: string; status: string }; timestamp: Date }
  | {
      type: 'reasoning_step';
      data: {
        phase: string;
        status: string;
        message: string;
        description?: string;
        details?: Record<string, unknown>;
      };
      timestamp: Date;
    };

export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  imageUrl?: string;
  timestamp: Date;
  steps?: AgentStep[];
  currentStatus?: string;
  verification_score?: number;
  metadata?: {
    execution_time?: number;
    route_used?: string;
    context_length?: number;
    emotional_state?: string;
    status?: string;
    // Memory & Context
    user_memory_facts?: string[];
    collective_memory_facts?: string[];
    golden_answer_used?: boolean;
    followup_questions?: string[];
    // Generated images from image generation tool
    generated_image?: string;
  };
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at?: string;
  message_count: number;
  preview?: string;
}

export interface UserMemoryContext {
  success: boolean;
  user_id: string;
  profile_facts: string[];
  summary?: string;
  counters: Record<string, number>;
  has_data: boolean;
  error?: string;
}
