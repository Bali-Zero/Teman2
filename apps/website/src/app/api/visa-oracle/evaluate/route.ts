import { forwardOracleEvaluation } from "../../../../features/visa-oracle/evaluate.server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: Request): Promise<Response> {
  return forwardOracleEvaluation(request);
}
