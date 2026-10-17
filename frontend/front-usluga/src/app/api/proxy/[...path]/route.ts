import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { TOKEN_COOKIE } from "@/lib/session";

const API_URL = (process.env.NURCRM_API_URL ?? "http://localhost").replace(/\/+$/, "");

async function forwardRequest(req: NextRequest, rawPath: string[]) {
  const jar = await cookies();
  const token = jar.get(TOKEN_COOKIE)?.value;
  let targetPath = rawPath.join("/");
  if (!targetPath.endsWith("/")) {
    targetPath += "/";
  }
  const search = req.nextUrl.search;
  const url = `${API_URL}/${targetPath}${search}`;

  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.text();
  }

  try {
    const res = await fetch(url, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
    });

    const responseText = await res.text();
    const responseHeaders = new Headers();
    responseHeaders.set("Content-Type", res.headers.get("content-type") || "application/json");

    return new NextResponse(responseText, {
      status: res.status,
      headers: responseHeaders,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Network error";
    return NextResponse.json({ error: "backend_unavailable", detail: msg }, { status: 502 });
  }
}

export async function GET(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path);
}

export async function POST(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path);
}

export async function PATCH(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path);
}

export async function PUT(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path);
}

export async function DELETE(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path);
}
