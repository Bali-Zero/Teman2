import { COLLECTION_NAMES } from "./constants";

/**
 * Generates a dynamic, context-aware status message for a tool being used.
 * Falls back to generic labels if specific info is missing.
 */
export function getDynamicToolMessage(
  toolName: string,
  args: any,
  defaultLabel: string
): string {
  try {
    switch (toolName) {
      case "vector_search":
      case "knowledge_graph_search":
        const query = args?.query || args?.q || "";
        const collection = args?.collection_name || "";
        const collectionDisplay = COLLECTION_NAMES[collection] || collection;

        if (query && collectionDisplay) {
          return `Searching for "${query}" in ${collectionDisplay}...`;
        }
        if (query) {
          return `Searching for "${query}"...`;
        }
        if (collectionDisplay) {
          return `Searching ${collectionDisplay}...`;
        }
        return "Searching knowledge base...";

      case "get_pricing":
        const service = args?.service_name || args?.query || "";
        return service
          ? `Retrieving price for "${service}"...`
          : "Fetching pricing information...";

      case "database_query":
        const docId = args?.document_id || "";
        return docId ? `Reading document ${docId}...` : "Reading full document...";

      case "web_search":
        const webQuery = args?.query || args?.q || "";
        return webQuery ? `Searching web for "${webQuery}"...` : "Searching the web...";

      case "generate_image":
        return "Generating image...";

      default:
        return defaultLabel;
    }
  } catch (e) {
    return defaultLabel;
  }
}
