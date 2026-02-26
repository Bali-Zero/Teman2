import { NextResponse } from "next/server";
import { getGoldCodes } from "@/lib/kbli-data.server";

export async function GET() {
  const codes = getGoldCodes();

  return NextResponse.json(
    { total: codes.length, codes },
    {
      headers: {
        "Cache-Control":
          "public, s-maxage=86400, stale-while-revalidate=604800",
      },
    },
  );
}
