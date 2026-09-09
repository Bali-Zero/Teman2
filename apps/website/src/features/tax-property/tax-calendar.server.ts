import {
  filterDeadlines,
  TAX_ARCHIVE,
  TAX_KINDS,
  TAX_REGENCIES,
  taxCalendarIcal,
} from "./tax-calendar";

function selectedRecords(request: Request) {
  const query = new URL(request.url).searchParams;
  const kind = query.get("kind") ?? "ALL",
    regency = query.get("regency") ?? "";
  if (
    !(TAX_KINDS as readonly string[]).includes(kind) ||
    (regency && !TAX_REGENCIES.includes(regency))
  )
    return null;
  return filterDeadlines(TAX_ARCHIVE, kind, regency);
}
export function getTaxDeadlines(request: Request): Response {
  const deadlines = selectedRecords(request);
  return deadlines
    ? Response.json(
        {
          status: "historical_unverified",
          verified_upcoming: false,
          deadlines,
          regencies: TAX_REGENCIES,
        },
        { headers: { "Cache-Control": "no-store" } },
      )
    : Response.json({ error: "invalid_filter" }, { status: 400 });
}
export function getTaxIcal(request: Request): Response {
  const deadlines = selectedRecords(request);
  if (!deadlines)
    return Response.json({ error: "invalid_filter" }, { status: 400 });
  return new Response(taxCalendarIcal(deadlines), {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="bali-tax-archive.ics"',
      "Cache-Control": "no-store",
    },
  });
}
