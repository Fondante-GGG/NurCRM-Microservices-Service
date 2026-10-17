import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { TOKEN_COOKIE, SUPPORT_TOKEN_COOKIE, SECTION_COOKIE, NAME_COOKIE } from "@/lib/session";

const API_URL = (process.env.NURCRM_API_URL ?? "http://localhost").replace(/\/+$/, "");

export async function POST(request: Request) {
  const jar = await cookies();
  const currentToken = jar.get(TOKEN_COOKIE)?.value;
  const supportToken = jar.get(SUPPORT_TOKEN_COOKIE)?.value;

  if (currentToken) {
    try {
      await fetch(`${API_URL}/api/support/impersonate/exit/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${currentToken}`,
          Accept: "application/json",
        },
        cache: "no-store",
      }).catch(() => {});
    } catch {}
  }

  const base = { httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 60 * 60 * 24 * 7, secure: process.env.NODE_ENV === "production" };

  if (supportToken) {
    // Restore support session
    jar.set(TOKEN_COOKIE, supportToken, base);
    jar.set(SECTION_COOKIE, "support", base);
    jar.set(NAME_COOKIE, "Поддержка", base);
    jar.delete(SUPPORT_TOKEN_COOKIE);
    return NextResponse.json({ ok: true, next: "/support" });
  }

  // If no saved support token, logout
  jar.delete(TOKEN_COOKIE);
  jar.delete(SECTION_COOKIE);
  jar.delete(NAME_COOKIE);
  jar.delete(SUPPORT_TOKEN_COOKIE);
  return NextResponse.json({ ok: true, next: "/login" });
}
