// src/proxy.ts
//
// Gerbang autentikasi SmartTwin (Next.js 16 "proxy" convention,
// pengganti middleware.ts).
//
// - Belum login  -> semua halaman privat dialihkan ke /login.
// - Sudah login  -> root dan halaman auth dialihkan ke /dashboard.

import { NextResponse, type NextRequest } from "next/server";

import { createMiddlewareClient } from "@/lib/supabase/middlewareClient";

const PUBLIC_ONLY_ROUTES = ["/login", "/register"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Khusus verifikasi browser lokal/CI. Tidak pernah aktif di production dan
  // default-nya tetap false, sehingga gerbang autentikasi normal tidak berubah.
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.SMARTTWIN_E2E_BYPASS_AUTH === "1"
  ) {
    return NextResponse.next();
  }

  const { supabase, getResponse } = createMiddlewareClient(request);

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const isPublicOnlyRoute = PUBLIC_ONLY_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );

  if (!user && pathname.startsWith("/api")) {
    return NextResponse.json({ error: "Belum login." }, { status: 401 });
  }

  if (!user && !isPublicOnlyRoute) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  if (user && (pathname === "/" || isPublicOnlyRoute)) {
    const dashboardUrl = new URL("/dashboard", request.url);
    return NextResponse.redirect(dashboardUrl);
  }

  const response = getResponse();

  if (user && !isPublicOnlyRoute) {
    response.headers.set("Cache-Control", "private, no-store, max-age=0");
  }

  return response;
}

export const config = {
  matcher: [
    /*
     * Jalankan middleware di semua route KECUALI:
     * - _next/static, _next/image
     * - favicon.ico
     * - file statis (svg, png, jpg, dst.)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
