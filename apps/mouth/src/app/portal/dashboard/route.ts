export function GET(request: Request): Response {
  const target = new URL(request.url);
  target.pathname = "/portal";

  return Response.redirect(target, 308);
}
