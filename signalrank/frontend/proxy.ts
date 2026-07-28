import { NextResponse } from "next/server";
import { auth } from "@/auth";

export default auth((request) => {
  const { pathname, search } = request.nextUrl;
  const desktopMode =
    process.env.SIGNALRANK_MODE === "desktop" ||
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";
  if (desktopMode || request.auth) return NextResponse.next();

  const destination = new URL(
    "/login",
    request.nextUrl.origin,
  );
  destination.searchParams.set("callbackUrl", `${pathname}${search}`);
  return NextResponse.redirect(destination);
});

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/jobs/:path*",
    "/tracker/:path*",
    "/settings/:path*",
    "/onboarding/:path*",
  ],
};
