import {
  Search,
  Database,
  Calculator,
  Globe,
  Users,
  Sparkles,
  BookOpen,
  Scale,
  Zap,
  Network,
  DollarSign,
  Brain,
} from "lucide-react";
import { ThinkingPhrase } from "./types";

// Collection display names for user-friendly messages
export const COLLECTION_NAMES: Record<string, string> = {
  visa_oracle: "documenti visti",
  legal_unified: "normativa legale",
  tax_genius: "regolamenti fiscali",
  kbli_2025_final: "codici KBLI",
  balizero_news: "aggiornamenti normativi",
  bali_zero_pricing_hybrid: "listino prezzi",
  training_conversations_hybrid: "conversazioni precedenti",
  immigration_circulars: "circolari immigrazione",
};

// Map tool names to icons
export const TOOL_ICONS: Record<string, React.ReactNode> = {
  vector_search: <Search className="w-3.5 h-3.5" />,
  knowledge_graph_search: <Network className="w-3.5 h-3.5" />,
  database_query: <Database className="w-3.5 h-3.5" />,
  web_search: <Globe className="w-3.5 h-3.5" />,
  calculator: <Calculator className="w-3.5 h-3.5" />,
  get_pricing: <DollarSign className="w-3.5 h-3.5" />,
  team_knowledge: <Users className="w-3.5 h-3.5" />,
  search_team_member: <Users className="w-3.5 h-3.5" />,
  get_team_members_list: <Users className="w-3.5 h-3.5" />,
  generate_image: <Sparkles className="w-3.5 h-3.5" />,
};

// Legacy static config for backward compatibility
export const TOOL_CONFIG: Record<
  string,
  { icon: React.ReactNode; label: string }
> = {
  vector_search: {
    icon: <Search className="w-3.5 h-3.5" />,
    label: "Searching Knowledge Base",
  },
  database_query: {
    icon: <Database className="w-3.5 h-3.5" />,
    label: "Reading Full Document",
  },
  web_search: {
    icon: <Globe className="w-3.5 h-3.5" />,
    label: "Searching the Web",
  },
  calculator: {
    icon: <Calculator className="w-3.5 h-3.5" />,
    label: "Calculating",
  },
  get_pricing: {
    icon: <DollarSign className="w-3.5 h-3.5" />,
    label: "Fetching Pricing Info",
  },
  team_knowledge: {
    icon: <Users className="w-3.5 h-3.5" />,
    label: "Looking Up Team Info",
  },
  graph_traversal: {
    icon: <Network className="w-3.5 h-3.5" />,
    label: "Exploring Knowledge Graph",
  },
  knowledge_graph_search: {
    icon: <Network className="w-3.5 h-3.5" />,
    label: "Exploring Knowledge Graph",
  },
};

export const DEFAULT_TOOL = {
  icon: <Brain className="w-3.5 h-3.5" />,
  label: "Processing",
};

// Fun thinking phrases that rotate
export const THINKING_PHRASES: ThinkingPhrase[] = [
  {
    text: "Analyzing your question...",
    icon: <Sparkles className="w-4 h-4" />,
  },
  {
    text: "Consulting Indonesian regulations...",
    icon: <Scale className="w-4 h-4" />,
  },
  {
    text: "Searching through documents...",
    icon: <BookOpen className="w-4 h-4" />,
  },
  {
    text: "Cross-referencing sources...",
    icon: <Search className="w-4 h-4" />,
  },
  { text: "Building your answer...", icon: <Zap className="w-4 h-4" /> },
];

// Indonesian interjections - casual, friendly phrases
export const INDONESIAN_INTERJECTIONS = [
  "Sabar ya, Pak/Bu...",
  "Ditunggu sebentar...",
  "Sedang diproses...",
  "Bentar lagi siap...",
  "Lagi dicari dulu...",
  "Mohon tunggu ya...",
  "Sebentar lagi...",
  "Santai dulu...",
];
