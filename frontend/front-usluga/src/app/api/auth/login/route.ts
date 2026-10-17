import { NextResponse } from "next/server";
import { login } from "@/lib/nurcrm";
import { setSession } from "@/lib/session";

// Браузер шлёт логин и пароль сюда, а не напрямую на сервер NurCRM:
// токен остаётся в httpOnly-cookie и в JavaScript страницы не попадает.
export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { login?: string; email?: string; password?: string };
  const loginValue = (body.login ?? body.email ?? "").trim();
  const password = body.password ?? "";
  if (!loginValue || !password) {
    return NextResponse.json({ error: "credentials" }, { status: 400 });
  }

  if (process.env.NURCRM_DEV_LOGIN === "1") {
    await setSession({ token: "dev", section: null, name: loginValue });
    return NextResponse.json({ next: "/razdel" });
  }

  const result = await login(loginValue, password);
  if (!result.ok) {
    if (result.status === 0) return NextResponse.json({ error: "network" }, { status: 502 });
    if (result.status === 400 || result.status === 401 || result.status === 403) {
      return NextResponse.json({ error: "credentials", detail: result.message }, { status: 401 });
    }
    return NextResponse.json({ error: "server", detail: result.message }, { status: 502 });
  }

  await setSession({ token: result.token, section: result.section, name: result.name });
  return NextResponse.json({ next: result.section ? `/${result.section}` : "/razdel" });
}
