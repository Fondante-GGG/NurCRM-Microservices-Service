import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { TOKEN_COOKIE, SUPPORT_TOKEN_COOKIE, SECTION_COOKIE, NAME_COOKIE } from "@/lib/session";

const API_URL = (process.env.NURCRM_API_URL ?? "http://localhost").replace(/\/+$/, "");

export async function POST(request: Request) {
  const jar = await cookies();
  const currentToken = jar.get(TOKEN_COOKIE)?.value;
  if (!currentToken) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = (await request.json().catch(() => ({}))) as { company_id?: string; agent_name?: string };
  const companyId = body.company_id;
  if (!companyId) {
    return NextResponse.json({ error: "company_id is required" }, { status: 400 });
  }

  try {
    const res = await fetch(`${API_URL}/api/support/companies/${companyId}/impersonate/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${currentToken}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json({ error: data.message || "Failed to impersonate" }, { status: res.status });
    }

    const impersonationToken = data.access_token || data.access || data.token;
    if (!impersonationToken) {
      return NextResponse.json({ error: "No impersonation token received" }, { status: 502 });
    }

    const base = { httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 3600, secure: process.env.NODE_ENV === "production" };
    // Keep support token for returning later
    jar.set(SUPPORT_TOKEN_COOKIE, currentToken, base);
    // Switch active session to impersonated token
    jar.set(TOKEN_COOKIE, impersonationToken, base);
    jar.set(SECTION_COOKIE, "usluga", base);
    jar.set(NAME_COOKIE, data.company_name || "Клиент (Поддержка)", base);

    return NextResponse.json({ ok: true, next: "/usluga/analitika" });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Network error";
    return NextResponse.json({ error: "network", detail: msg }, { status: 502 });
  }
}
