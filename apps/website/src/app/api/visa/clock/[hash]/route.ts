import { publicVisaRequest } from "../../../../../features/visa-tools/public-api";
export const dynamic = "force-dynamic";
export async function GET(
  request: Request,
  { params }: { params: Promise<{ hash: string }> },
) {
  const { hash } = await params;
  return publicVisaRequest(request, "clock", hash);
}
