import { getAllCodes } from "@/lib/kbli-data";
import { buildKbliLightIndex } from "@/lib/kbli-light-index";

// Emitted once at build time from the dataset the code pages render; the
// Navigator search fetches it for its instant first pass (lib/kbli-light-index.ts).
export const dynamic = "force-static";

export function GET() {
  return Response.json(buildKbliLightIndex(getAllCodes()), {
    headers: { "Cache-Control": "public, max-age=3600, s-maxage=86400" },
  });
}
