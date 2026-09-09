function alias(request: Request): Response {
  const destination = new URL(request.url);
  destination.pathname = "/taxes/gap";
  return Response.redirect(destination, 307);
}
export const GET = alias;
export const HEAD = alias;
