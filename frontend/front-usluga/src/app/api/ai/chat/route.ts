import { NextRequest, NextResponse } from "next/server";
import { executeAiFallbackChain, type ChatMessage, type ServicesContext } from "@/lib/ai-service";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const message = typeof body.message === "string" ? body.message.trim() : "";
    if (!message) {
      return NextResponse.json({ error: "missing_message", message: "Сообщение не может быть пустым" }, { status: 400 });
    }

    const rawHistory: any[] = Array.isArray(body.history) ? body.history : [];
    const history: ChatMessage[] = rawHistory
      .filter((h) => h && (h.role === "user" || h.role === "assistant") && typeof h.content === "string")
      .map((h) => ({ role: h.role, content: h.content }));

    const messages: ChatMessage[] = [
      ...history,
      { role: "user", content: message },
    ];

    const context: ServicesContext = body.context || {};
    const mockDown: string[] = Array.isArray(body.mockDown) ? body.mockDown : [];

    const result = await executeAiFallbackChain(messages, context, mockDown);

    if (result.maintenance) {
      return NextResponse.json({
        ok: false,
        maintenance: true,
        message: result.message,
        errors: result.errors,
      }, { status: 200 }); // Return 200 with maintenance payload so UI smoothly renders maintenance state
    }

    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json({
      ok: false,
      maintenance: true,
      message: "Ведутся технические работы. Пожалуйста, обратитесь позже или свяжитесь с поддержкой.",
      error: err?.message || "Internal error",
    }, { status: 200 });
  }
}
