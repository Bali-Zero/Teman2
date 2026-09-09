import {
  catalogSearch,
  getCode,
  publicItem,
} from "../../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export function GET(request: Request): Response {
  const params = new URL(request.url).searchParams;
  const codes = params.get("codes");
  if (codes !== null) {
    const values = [...new Set(codes.split(","))];
    if (values.length > 6 || values.some((code) => !/^\d{5}$/.test(code)))
      return Response.json(
        { error: "Choose up to six five-digit codes." },
        { status: 400 },
      );
    const items = values.flatMap((id) => {
      const code = getCode(id);
      return code ? [publicItem(code)] : [];
    });
    return Response.json(
      { items },
      { headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(catalogSearch(Object.fromEntries(params)), {
    headers: { "Cache-Control": "no-store" },
  });
}
