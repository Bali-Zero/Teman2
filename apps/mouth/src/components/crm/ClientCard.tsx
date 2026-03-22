import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  MessageCircle,
  Clock,
  MoreHorizontal,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Mail,
  Phone,
} from "lucide-react";
import { Client } from "@/lib/api/crm/crm.types";
import { useRouter } from "next/navigation";

interface ClientCardProps {
  client: Client;
  isDragging?: boolean;
}

const SENTIMENT_COLORS = {
  positive: "ring-green-500",
  neutral: "ring-yellow-500",
  negative: "ring-red-500",
  mixed: "ring-purple-500",
  none: "ring-gray-200 dark:ring-gray-700",
};

const SENTIMENT_BG = {
  positive: "bg-green-500/10 text-green-600 dark:text-green-400",
  neutral: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  negative: "bg-red-500/10 text-red-600 dark:text-red-400",
  mixed: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  none: "bg-gray-100 dark:bg-gray-800 text-gray-500",
};

// Map nationalities to flag emojis
const NATIONALITY_FLAGS: Record<string, string> = {
  Italian: "🇮🇹",
  Italy: "🇮🇹",
  Russian: "🇷🇺",
  Russia: "🇷🇺",
  Ukrainian: "🇺🇦",
  Ukraine: "🇺🇦",
  American: "🇺🇸",
  USA: "🇺🇸",
  "United States": "🇺🇸",
  British: "🇬🇧",
  UK: "🇬🇧",
  "United Kingdom": "🇬🇧",
  Australian: "🇦🇺",
  Australia: "🇦🇺",
  German: "🇩🇪",
  Germany: "🇩🇪",
  French: "🇫🇷",
  France: "🇫🇷",
  Spanish: "🇪🇸",
  Spain: "🇪🇸",
  Dutch: "🇳🇱",
  Netherlands: "🇳🇱",
  Indonesian: "🇮🇩",
  Indonesia: "🇮🇩",
  Chinese: "🇨🇳",
  China: "🇨🇳",
  Japanese: "🇯🇵",
  Japan: "🇯🇵",
  Korean: "🇰🇷",
  Korea: "🇰🇷",
  "South Korea": "🇰🇷",
  Indian: "🇮🇳",
  India: "🇮🇳",
  Brazilian: "🇧🇷",
  Brazil: "🇧🇷",
  Canadian: "🇨🇦",
  Canada: "🇨🇦",
  Mexican: "🇲🇽",
  Mexico: "🇲🇽",
  Argentinian: "🇦🇷",
  Argentina: "🇦🇷",
  "South African": "🇿🇦",
  "South Africa": "🇿🇦",
  "New Zealander": "🇳🇿",
  "New Zealand": "🇳🇿",
  Irish: "🇮🇪",
  Ireland: "🇮🇪",
  Portuguese: "🇵🇹",
  Portugal: "🇵🇹",
  Polish: "🇵🇱",
  Poland: "🇵🇱",
  Turkish: "🇹🇷",
  Turkey: "🇹🇷",
  Thai: "🇹🇭",
  Thailand: "🇹🇭",
  Vietnamese: "🇻🇳",
  Vietnam: "🇻🇳",
  Filipino: "🇵🇭",
  Philippines: "🇵🇭",
  Malaysian: "🇲🇾",
  Malaysia: "🇲🇾",
  Singaporean: "🇸🇬",
  Singapore: "🇸🇬",
  // Additional nationalities / aliases found in CRM data
  Hellenic: "🇬🇷",
  "British Citizen": "🇬🇧",
  Española: "🇪🇸",
  Française: "🇫🇷",
  Emirati: "🇦🇪",
  "United Arab Emirates": "🇦🇪",
  Colombian: "🇨🇴",
  Colombia: "🇨🇴",
  Argentine: "🇦🇷",
  Venezuelan: "🇻🇪",
  Venezuela: "🇻🇪",
  Belgian: "🇧🇪",
  Belgium: "🇧🇪",
  Austrian: "🇦🇹",
  Austria: "🇦🇹",
  Czech: "🇨🇿",
  Romanian: "🇷🇴",
  Romania: "🇷🇴",
  Hungarian: "🇭🇺",
  Hungary: "🇭🇺",
  Croatian: "🇭🇷",
  Croatia: "🇭🇷",
  Serbian: "🇷🇸",
  Serbia: "🇷🇸",
  Bulgarian: "🇧🇬",
  Bulgaria: "🇧🇬",
  Taiwanese: "🇹🇼",
  Taiwan: "🇹🇼",
  Lebanese: "🇱🇧",
  Lebanon: "🇱🇧",
  Israeli: "🇮🇱",
  Israel: "🇮🇱",
  "South Korean": "🇰🇷",
  THA: "🇹🇭",
};

// Get flag emoji from nationality (case-insensitive)
const getCountryFlag = (nationality: string | undefined): string | null => {
  if (!nationality) return null;
  // Direct match
  if (NATIONALITY_FLAGS[nationality]) return NATIONALITY_FLAGS[nationality];
  // Case-insensitive: try Title Case
  const titleCase =
    nationality.charAt(0).toUpperCase() + nationality.slice(1).toLowerCase();
  if (NATIONALITY_FLAGS[titleCase]) return NATIONALITY_FLAGS[titleCase];
  // Try each key
  const lower = nationality.toLowerCase();
  for (const [key, flag] of Object.entries(NATIONALITY_FLAGS)) {
    if (key.toLowerCase() === lower) return flag;
  }
  return null;
};

export const ClientCard = React.memo(
  ({ client, isDragging }: ClientCardProps) => {
    const router = useRouter();
    const [isMounted, setIsMounted] = useState(false);

    // Fix hydration mismatch: only render dates on client
    useEffect(() => {
      setIsMounted(true);
    }, []);

    // Determine sentiment aura
    const sentiment = (
      client.last_sentiment || "none"
    ).toLowerCase() as keyof typeof SENTIMENT_COLORS;
    const ringColor = SENTIMENT_COLORS[sentiment] || SENTIMENT_COLORS.none;
    const badgeStyle = SENTIMENT_BG[sentiment] || SENTIMENT_BG.none;

    // Get country flag for fallback
    const countryFlag = getCountryFlag(client.nationality);

    return (
      <div className="relative group perspective-1000">
        <motion.div
          // Removed layoutId to improve performance with large lists
          // layoutId causes expensive layout calculations with many items
          className={`
          relative rounded-xl border p-4 cursor-pointer transition-all duration-300 shadow-lg backdrop-blur-xl
          ${isDragging ? "opacity-50 scale-95 rotate-3" : "hover:-translate-y-1 hover:shadow-2xl hover:bg-[rgba(45,45,50,0.65)]"}
        `}
          style={{
            background: "rgba(35, 35, 40, 0.55)",
            borderColor: "rgba(255, 255, 255, 0.05)",
          }}
          onClick={() => router.push(`/clients/${client.id}`)}
        >
          {/* Header with Avatar & Name */}
          <div className="flex items-start gap-3 mb-3">
            <div
              className={`relative w-10 h-10 rounded-full ${ringColor} ring-2 ring-offset-2 ring-offset-[var(--background-secondary)]`}
            >
              {client.avatar_url ? (
                <img
                  src={client.avatar_url}
                  alt={client.full_name}
                  className="w-full h-full rounded-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : null}
              {!client.avatar_url && (
                <div className="w-full h-full rounded-full bg-[var(--background)] flex items-center justify-center">
                  {countryFlag ? (
                    <span className="text-lg leading-none">{countryFlag}</span>
                  ) : (
                    <span className="text-xs font-bold text-[var(--foreground)] opacity-60">
                      {client.full_name
                        ?.split(" ")
                        .slice(0, 2)
                        .map((n) => n[0]?.toUpperCase())
                        .join("") || "?"}
                    </span>
                  )}
                </div>
              )}

              {/* Status Dot */}
              <div
                className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-[var(--background-secondary)]
              ${
                {
                  lead: "bg-blue-500",
                  active: "bg-green-500",
                  completed: "bg-purple-500",
                  inactive: "bg-gray-500",
                  lost: "bg-red-500",
                }[client.status] || "bg-gray-400"
              }`}
              />
            </div>

            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-[var(--foreground)] truncate">
                {client.full_name}
              </h4>
              <div className="flex items-center gap-2 text-xs text-[var(--foreground-muted)]">
                <span className="truncate">
                  {client.nationality || "Unknown"}
                </span>
                {client.company_name && (
                  <>
                    <span>•</span>
                    <span className="truncate max-w-[80px]">
                      {client.company_name}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Strategic Peek Info (Always visible in card, but stylized) */}
          <div className="space-y-2 text-xs">
            {/* Last Interaction Summary */}
            {client.last_interaction_summary ? (
              <div className={`p-2 rounded-lg ${badgeStyle} line-clamp-2`}>
                <div className="flex items-center gap-1.5 mb-1 opacity-75">
                  <MessageCircle className="w-3 h-3" />
                  <span className="font-medium capitalize">
                    {sentiment} Interaction
                  </span>
                </div>
                "{client.last_interaction_summary}"
              </div>
            ) : (
              <div className="p-2 rounded-lg bg-[var(--background)] text-[var(--foreground-muted)] italic">
                No recent interactions
              </div>
            )}

            {/* Quick Stats Row */}
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[var(--foreground-muted)]">
              <div className="flex items-center gap-1.5" title="Last Contact">
                <Clock className="w-3 h-3" />
                <span>
                  {client.last_interaction_date
                    ? isMounted
                      ? new Date(
                          client.last_interaction_date,
                        ).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })
                      : "..."
                    : "Never"}
                </span>
              </div>

              {/* Action Buttons (Visible on Hover) */}
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="p-1 hover:text-[var(--accent)] transition-colors">
                  <Mail className="w-3 h-3" />
                </button>
                <button className="p-1 hover:text-green-500 transition-colors">
                  <Phone className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        </motion.div>

        {/* "Strategic Peek" Hover Effect - Shows sentiment on hover */}
        <div className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-48 opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 translate-y-2 group-hover:translate-y-0">
          <div className="bg-black/90 backdrop-blur-md text-white p-3 rounded-lg shadow-xl text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-400">Sentiment:</span>
              <span className="capitalize text-white font-medium">
                {sentiment}
              </span>
            </div>
            <div className="absolute bottom-[-4px] left-1/2 -translate-x-1/2 w-2 h-2 bg-black/90 rotate-45"></div>
          </div>
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    // Only re-render if client data or dragging state changes
    return (
      prevProps.client.id === nextProps.client.id &&
      prevProps.client.last_sentiment === nextProps.client.last_sentiment &&
      prevProps.client.last_interaction_date ===
        nextProps.client.last_interaction_date &&
      prevProps.client.last_interaction_summary ===
        nextProps.client.last_interaction_summary &&
      prevProps.isDragging === nextProps.isDragging
    );
  },
);
