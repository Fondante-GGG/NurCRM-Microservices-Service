import { NextResponse } from "next/server";
import { clearSession } from "@/lib/session";

export async function POST(request: Request) {
  await clearSession();
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "stage.nurcrm.kg";
  const proto = request.headers.get("x-forwarded-proto") || "https";
  return NextResponse.redirect(`${proto}://${host}/login`, { status: 303 });
}
