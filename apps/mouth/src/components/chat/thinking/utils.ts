import { COLLECTION_NAMES, TOOL_ICONS, DEFAULT_TOOL } from "./constants";
import { GenericStep, Activity } from "./types";

/**
 * Generate dynamic status message based on tool and arguments
 */
export function getDynamicToolMessage(
  toolName: string,
  args: Record<string, unknown>,
): string {
  const query = typeof args?.query === "string" ? args.query : "";
  const collection =
    typeof args?.collection === "string" ? args.collection : "";
  const shortQuery = query.length > 40 ? query.slice(0, 40) + "..." : query;

  switch (toolName) {
    case "vector_search": {
      if (collection && COLLECTION_NAMES[collection]) {
        return `Searching for "${shortQuery}" in ${COLLECTION_NAMES[collection]}...`;
      }
      return `Searching for "${shortQuery}" in knowledge base...`;
    }
    case "knowledge_graph_search": {
      const entity =
        typeof args?.entity_name === "string" ? args.entity_name : query;
      return `Exploring connections for "${entity}"...`;
    }
    case "calculator": {
      const expr = typeof args?.expression === "string" ? args.expression : "";
      return `Calculating: ${expr.slice(0, 30)}${expr.length > 30 ? "..." : ""}`;
    }
    case "get_pricing": {
      const service =
        typeof args?.service_name === "string" ? args.service_name : "service";
      return `Fetching price for "${service}"...`;
    }
    case "team_knowledge":
    case "search_team_member":
    case "get_team_members_list": {
      return "Consulting Bali Zero team...";
    }
    case "web_search": {
      return `Searching the web: "${shortQuery}"...`;
    }
    case "generate_image": {
      return "Generating image...";
    }
    default:
      return `Processing with ${toolName}...`;
  }
}

/**
 * Build activity list from steps with dynamic messages
 */
export function buildActivities(
  toolCalls: GenericStep[],
  toolEnds: GenericStep[],
): Activity[] {
  return toolCalls
    .map((step, idx) => {
      const stepData = step.data as Record<string, unknown> | undefined;
      const toolName =
        (stepData?.tool as string) || (stepData?.name as string) || "unknown";
      const toolArgs = (stepData?.args as Record<string, unknown>) || {};
      const icon = TOOL_ICONS[toolName] || DEFAULT_TOOL.icon;
      const dynamicLabel = getDynamicToolMessage(toolName, toolArgs);
      const isCompleted = idx < toolEnds.length;
      const isCurrent = idx === toolCalls.length - 1 && !isCompleted;

      return {
        key: `${toolName}-${idx}`,
        icon,
        label: dynamicLabel,
        toolName,
        isCompleted,
        isCurrent,
      };
    })
    .filter(Boolean);
}
