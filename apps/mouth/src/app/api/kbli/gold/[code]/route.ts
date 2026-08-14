import { NextResponse } from "next/server";
import { getCode, getGoldContent } from "@/lib/kbli-data.server";
import { discloseKbliEditorial } from "@/lib/kbli-pma-editorial";
import { isPmaVerdictVerified } from "@/lib/kbli-provenance";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ code: string }> },
) {
  const { code } = await params;

  if (!code || !/^\d{5}$/.test(code)) {
    return NextResponse.json(
      { error: "Invalid KBLI code. Must be 5 digits." },
      { status: 400 },
    );
  }

  const goldContent = getGoldContent(code);
  const codeData = getCode(code);

  if (!goldContent && !codeData) {
    return NextResponse.json(
      { error: `KBLI code ${code} not found` },
      { status: 404 },
    );
  }

  const pmaVerified = codeData ? isPmaVerdictVerified(codeData) : false;
  const publicEditorial = codeData
    ? discloseKbliEditorial(codeData, goldContent)
    : { gold: null };

  return NextResponse.json(
    {
      code,
      title: codeData?.titleId ?? null,
      pma: pmaVerified ? codeData?.pma : null,
      pma_provenance: codeData?.provenance?.pma ?? null,
      tier: codeData?.tier ?? "bronze",
      content: publicEditorial.gold,
    },
    {
      headers: {
        "Cache-Control":
          "public, s-maxage=86400, stale-while-revalidate=604800",
      },
    },
  );
}
