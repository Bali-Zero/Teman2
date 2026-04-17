import { NextResponse } from "next/server";
import { TAX_DEADLINES, getRegencies } from "../deadlines";

export async function GET() {
  return NextResponse.json({
    deadlines: TAX_DEADLINES,
    regencies: getRegencies(),
  });
}
