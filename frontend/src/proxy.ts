// src/proxy.ts
//
// Gerbang autentikasi SmartTwin (Next.js 16 "proxy" convention,
// pengganti middleware.ts).
//
// - Belum login  -> semua halaman dialihkan ke /login
//                   (termasuk "/" saat pertama kali masuk).
// - Sudah login   -> /login dan /register dialihkan ke "/".

import { NextResponse, type NextRequest } from "next/server";

import { createMiddlewareClient } from "@/lib/supabase/middlewareClient";

const PUBLIC_ONLY_ROUTES = ["/login", "/register"];

export async function proxy(request: NextRequest) {
  const { supabase, getResponse } = createMiddlewareClient(request);

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  const isPublicOnlyRoute = PUBLIC_ONLY_ROUTES.some((route) =>
    pathname.startsWith(route)
  );

  if (!user && pathname.startsWith("/api")) {
    return NextResponse.json({ error: "Belum login." }, { status: 401 });
  }

  if (!user && !isPublicOnlyRoute) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  if (user && isPublicOnlyRoute) {
    const homeUrl = new URL("/", request.url);
    return NextResponse.redirect(homeUrl);
  }

  return getResponse();
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
