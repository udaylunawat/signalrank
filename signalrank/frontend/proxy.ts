import { NextResponse } from "next/server";
import { auth } from "@/auth";

const desktopMode =
  process.env.SIGNALRANK_MODE === "desktop" ||
  process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";

const authenticatedProxy = auth((request) => {
  if (request.auth) return NextResponse.next();

  const { pathname, search } = request.nextUrl;
  const destination = new URL("/login", request.nextUrl.origin);
  destination.searchParams.set("callbackUrl", `${pathname}${search}`);
  return NextResponse.redirect(destination);
});

export default desktopMode ? () => NextResponse.next() : authenticatedProxy;

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/jobs/:path*",
    "/tracker/:path*",
    "/settings/:path*",
    "/onboarding/:path*",
  ],
};
