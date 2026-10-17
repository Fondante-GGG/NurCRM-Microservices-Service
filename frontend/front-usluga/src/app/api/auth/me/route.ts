import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { TOKEN_COOKIE } from "@/lib/session";

const API_URL = (process.env.NURCRM_API_URL ?? "http://localhost").replace(/\/+$/, "");

export async function GET() {
  const jar = await cookies();
  const token = jar.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${API_URL}/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      cache: "no-store",
    });

    if (!res.ok) {
      return NextResponse.json({ error: "error_from_backend", status: res.status }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Network error";
    return NextResponse.json({ error: "network", detail: msg }, { status: 502 });
  }
}
