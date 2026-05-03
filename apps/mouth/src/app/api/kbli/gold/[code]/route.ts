import { NextResponse } from "next/server";
import { getCode, getGoldContent } from "@/lib/kbli-data.server";

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

  return NextResponse.json(
    {
      code,
      title: codeData?.titleId ?? null,
      pma: codeData?.pma ?? null,
      tier: codeData?.tier ?? "bronze",
      content: goldContent,
    },
    {
      headers: {
        "Cache-Control":
          "public, s-maxage=86400, stale-while-revalidate=604800",
      },
    },
  );
}
