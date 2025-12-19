// Backend clock response
export interface ClockResponse {
  success: boolean;
  action?: string;
  timestamp?: string;
  bali_time?: string;
  message: string;
  error?: string;
  hours_worked?: number;
}

// Backend user status response
export interface UserStatusResponse {
  user_id: string;
  is_online: boolean;
  last_action: string | null;
  last_action_type: string | null;
  today_hours: number;
  week_hours: number;
  week_days: number;
}

