import { NextResponse, type NextRequest } from "next/server";
import { AUTH_ENABLED, DEFAULT_SECTION } from "@/lib/config";
import { isSection } from "@/lib/sections";

const TOKEN_COOKIE = "nurcrm_token";
const SECTION_COOKIE = "nurcrm_section";

// Без входа — только /login. После входа /login и / ведут в свой раздел.
// Пока вход спрятан, всё ведёт в программу по умолчанию.
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!AUTH_ENABLED) {
    if (pathname === "/" || pathname === "/login" || pathname === "/razdel") {
      return NextResponse.redirect(new URL(`/${DEFAULT_SECTION}`, request.url));
    }
    return NextResponse.next();
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  const section = request.cookies.get(SECTION_COOKIE)?.value;
  const home = isSection(section) ? `/${section}` : "/razdel";

  if (!token) {
    if (pathname === "/login") return NextResponse.next();
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (pathname === "/login" || pathname === "/") {
    return NextResponse.redirect(new URL(home, request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login", "/razdel", "/usluga/:path*", "/sklad/:path*", "/market/:path*", "/proizvodstvo/:path*", "/support", "/support/:path*"],
};
