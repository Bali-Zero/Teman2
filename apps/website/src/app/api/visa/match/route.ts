import { publicVisaRequest } from "../../../../features/visa-tools/public-api";
export const dynamic = "force-dynamic";
export function POST(request: Request) {
  return publicVisaRequest(request, "match");
}
