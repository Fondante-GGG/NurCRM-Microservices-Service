import { NextResponse, type NextRequest } from "next/server";
import { AUTH_ENABLED, DEFAULT_SECTION } from "@/lib/config";
import { isSection } from "@/lib/sections";

const TOKEN_COOKIE = "nurcrm_token";
const SECTION_COOKIE = "nurcrm_section";

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const jsonStr = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(jsonStr);
    if (payload.exp && typeof payload.exp === "number") {
      return Date.now() >= payload.exp * 1000;
    }
    return false;
  } catch {
    return false;
  }
}

function getBaseUrl(request: NextRequest): string {
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "stage.nurcrm.kg";
  const proto = request.headers.get("x-forwarded-proto") || "https";
  return `${proto}://${host}`;
}

// Без входа — только /login. После входа /login и / ведут в свой раздел.
// Пока вход спрятан, всё ведёт в программу по умолчанию.
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const baseUrl = getBaseUrl(request);

  if (!AUTH_ENABLED) {
    if (pathname === "/" || pathname === "/login" || pathname === "/razdel") {
      return NextResponse.redirect(new URL(`/${DEFAULT_SECTION}`, baseUrl));
    }
    return NextResponse.next();
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  const section = request.cookies.get(SECTION_COOKIE)?.value;
  const home = isSection(section) ? `/${section}` : "/razdel";

  if (!token || isTokenExpired(token)) {
    if (pathname === "/login" || pathname === "/") return NextResponse.next();
    const res = NextResponse.redirect(new URL("/login", baseUrl));
    res.cookies.delete(TOKEN_COOKIE);
    res.cookies.delete(SECTION_COOKIE);
    return res;
  }

  if (pathname === "/login" || pathname === "/") {
    return NextResponse.redirect(new URL(home, baseUrl));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login", "/razdel", "/usluga/:path*", "/sklad/:path*", "/market/:path*", "/proizvodstvo/:path*", "/support", "/support/:path*"],
};
