import { AgentStep } from "@/types";

// Generic step type for flexible event handling
export interface GenericStep {
  type: string;
  data?: unknown;
  timestamp?: Date;
}

export interface ThinkingIndicatorProps {
  isVisible: boolean;
  currentStatus?: string;
  steps?: GenericStep[] | AgentStep[];
  elapsedTime?: number;
  maxSteps?: number;
  currentStep?: number;
}

export interface Activity {
  key: string;
  icon: React.ReactNode;
  label: string;
  toolName: string;
  isCompleted: boolean;
  isCurrent: boolean;
}

export interface ThinkingPhrase {
  text: string;
  icon: React.ReactNode;
}
