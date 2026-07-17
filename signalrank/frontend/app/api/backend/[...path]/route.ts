import { NextRequest } from "next/server";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function backendOrigin() {
  const configured =
    process.env.BACKEND_URL ??
    process.env.API_URL_SERVER ??
    process.env.NEXT_PUBLIC_API_URL;
  if (process.env.SIGNALRANK_MODE === "desktop" && !configured) {
    throw new Error("BACKEND_URL is required in desktop mode");
  }
  return (configured ?? "http://localhost:8000").replace(/\/+$/, "");
}

function forwardHeaders(request: NextRequest) {
  const headers = new Headers(request.headers);
  for (const header of HOP_BY_HOP_HEADERS) headers.delete(header);
  headers.delete("accept-encoding");
  headers.delete("x-signalrank-desktop-token");
  if (process.env.SIGNALRANK_MODE === "desktop") {
    const bootstrapToken = process.env.SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN;
    if (!bootstrapToken) {
      throw new Error("Desktop bootstrap token is unavailable");
    }
    headers.set("X-SignalRank-Desktop-Token", bootstrapToken);
  }
  return headers;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  try {
    const { path } = await context.params;
    const targetPath = path.map(encodeURIComponent).join("/");
    const incomingUrl = new URL(request.url);
    const target = `${backendOrigin()}/${targetPath}${incomingUrl.search}`;
    const method = request.method.toUpperCase();
    const body =
      method === "GET" || method === "HEAD"
        ? undefined
        : await request.arrayBuffer();
    const upstream = await fetch(target, {
      method,
      headers: forwardHeaders(request),
      body,
      redirect: "manual",
      cache: "no-store",
    });
    const headers = new Headers(upstream.headers);
    for (const header of HOP_BY_HOP_HEADERS) headers.delete(header);
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend unavailable";
    return Response.json({ detail: message }, { status: 502 });
  }
}

export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
