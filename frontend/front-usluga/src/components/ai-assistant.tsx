"use client";

import { useState, useRef, useEffect } from "react";
import { Icon } from "./icon";
import { useStore } from "@/data/store";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  provider?: "gemini" | "claude" | "openai";
  isMaintenance?: boolean;
  time: string;
};

const SUGGESTIONS = [
  "💇‍♂️ Какие есть мужские стрижки и цены?",
  "⏱ Сколько длится стрижка бороды?",
  "⭐ Кто работает в салоне?",
  "📅 Как записаться на приём?",
];

export function AiAssistantWidget() {
  const { db } = useStore();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeProvider, setActiveProvider] = useState<"gemini" | "claude" | "openai" | null>(null);
  const [isMaintenance, setIsMaintenance] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Здравствуйте! Я ваш AI-ассистент по услугам. Могу подсказать актуальные цены, длительность процедур, мастеров и правила записи. Чем могу помочь?",
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (open) {
      scrollToBottom();
    }
  }, [messages, open]);

  const sendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: String(Date.now()),
      role: "user",
      content: text,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setIsMaintenance(false);

    // Prepare context from active CRM store
    const context = {
      companyName: db?.settings?.company?.name || "NurCRM Услуги",
      industry: db?.industry || "Сфера услуг / салон",
      intake: db?.intake || "schedule",
      branches: (db?.branches || []).map((b) => ({
        name: b.name,
        address: b.address,
        phone: b.phone,
        hours: b.hours,
      })),
      services: (db?.services || []).map((s) => ({
        name: s.name,
        price: s.price,
        duration: s.duration,
        category: (db?.categories || []).find((c) => c.id === s.categoryId)?.name || "Основная",
      })),
      staff: (db?.staff || []).map((st) => ({
        name: st.name,
        role: st.role,
        position: st.positionId || "Мастер",
      })),
    };

    const historyPayload = messages.slice(-8).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: historyPayload,
          context,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (data.maintenance || !data.ok) {
        setIsMaintenance(true);
        setActiveProvider(null);
        setMessages((prev) => [
          ...prev,
          {
            id: String(Date.now() + 1),
            role: "assistant",
            content: data.message || "Ведутся технические работы. Пожалуйста, обратитесь позже или свяжитесь с поддержкой.",
            isMaintenance: true,
            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      } else {
        setActiveProvider(data.provider || null);
        setMessages((prev) => [
          ...prev,
          {
            id: String(Date.now() + 1),
            role: "assistant",
            content: data.reply || "Готово.",
            provider: data.provider,
            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      }
    } catch {
      setIsMaintenance(true);
      setActiveProvider(null);
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: "assistant",
          content: "Ведутся технические работы. Пожалуйста, обратитесь позже или свяжитесь с поддержкой.",
          isMaintenance: true,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const resetChat = () => {
    setActiveProvider(null);
    setIsMaintenance(false);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "Здравствуйте! Я ваш AI-ассистент по услугам. Могу подсказать актуальные цены, длительность процедур, мастеров и правила записи. Чем могу помочь?",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  const getProviderBadge = (provider?: "gemini" | "claude" | "openai") => {
    if (provider === "gemini") {
      return <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-blue-600">Gemini</span>;
    }
    if (provider === "claude") {
      return <span className="inline-flex items-center gap-1 rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-purple-600">Claude</span>;
    }
    if (provider === "openai") {
      return <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600">Codex / GPT</span>;
    }
    return null;
  };

  return (
    <>
      {/* Floating Trigger Button in bottom-right corner */}
      <div className="fixed bottom-5 right-5 z-50">
        {!open ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Открыть AI-помощника"
            className="group press flex items-center gap-2.5 rounded-full bg-gradient-to-r from-primary to-primary-deep px-4 py-3 text-white shadow-xl shadow-primary/20 ring-2 ring-gold/80 transition-all hover:scale-105 hover:ring-4 hover:ring-gold"
          >
            <span className="flex size-7 items-center justify-center rounded-full bg-gold text-primary shadow-sm">
              <Icon name="sparkles" className="size-4 animate-pulse" />
            </span>
            <span className="text-sm font-bold tracking-tight">AI-Помощник</span>
            <span className="relative flex size-2.5">
              <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${isMaintenance ? "bg-danger" : "bg-gold"}`} />
              <span className={`relative inline-flex size-2.5 rounded-full ${isMaintenance ? "bg-danger" : "bg-positive"}`} />
            </span>
          </button>
        ) : null}
      </div>

      {/* Floating Chat Modal */}
      {open && (
        <div className="fixed bottom-5 right-5 z-50 flex h-[580px] max-h-[85vh] w-[94vw] sm:w-[420px] flex-col overflow-hidden rounded-2xl border border-line bg-card shadow-2xl anim-pop">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-line bg-nav px-4 py-3 text-white">
            <div className="flex items-center gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gold text-primary">
                <Icon name="sparkles" className="size-4" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold leading-tight">AI-Консультант</h3>
                  <span className="rounded bg-gold/20 px-1.5 py-0.2 text-[10px] font-extrabold text-gold">Услуги</span>
                </div>
                <div className="text-[11px] text-nav-muted">
                  {activeProvider ? (
                    <span className="text-emerald-300">Провайдер: {activeProvider === "gemini" ? "Gemini" : activeProvider === "claude" ? "Claude" : "Codex/OpenAI"}</span>
                  ) : (
                    "Служба онлайн-ответов"
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 text-nav-text">
              <button
                type="button"
                onClick={resetChat}
                title="Очистить диалог"
                className="press rounded-lg p-1.5 hover:bg-white/10 hover:text-white"
              >
                <Icon name="history" className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Закрыть"
                title="Закрыть"
                className="press rounded-lg p-1.5 hover:bg-white/10 hover:text-white"
              >
                <Icon name="x" className="size-5" />
              </button>
            </div>
          </div>

          {/* Maintenance Alert Card */}
          {isMaintenance && (
            <div className="border-b border-danger/20 bg-bad-soft px-4 py-2.5 text-xs text-danger anim-fade-in">
              <div className="flex items-center gap-1.5 font-bold">
                <span>⚠️</span>
                <span>Техническое обслуживание</span>
              </div>
              <p className="mt-0.5 text-ink-mid">
                Все AI-провайдеры временно недоступны. Ведутся технические работы. Пожалуйста, обратитесь позже или свяжитесь с поддержкой.
              </p>
            </div>
          )}

          {/* Messages Area */}
          <div className="flex-1 space-y-3 overflow-y-auto bg-paper/60 p-4 [scrollbar-width:thin]">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"} anim-rise`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "rounded-br-sm bg-primary text-white shadow-sm"
                      : m.isMaintenance
                      ? "rounded-bl-sm border border-danger/30 bg-bad-soft text-danger"
                      : "rounded-bl-sm border border-line bg-card text-ink shadow-sm"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>

                <div className="mt-1 flex items-center gap-2 px-1 text-[10px] text-ink-soft">
                  <span>{m.time}</span>
                  {m.provider && getProviderBadge(m.provider)}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-line bg-card px-3.5 py-2.5 text-xs text-ink-soft shadow-sm max-w-[70%] anim-fade-in">
                <span className="size-2 animate-bounce rounded-full bg-gold" />
                <span className="size-2 animate-bounce rounded-full bg-primary [animation-delay:150ms]" />
                <span className="size-2 animate-bounce rounded-full bg-gold [animation-delay:300ms]" />
                <span className="ml-1 text-[11px] font-medium">AI готовит ответ...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions chips */}
          {messages.length <= 3 && !loading && (
            <div className="flex gap-1.5 overflow-x-auto border-t border-line/60 bg-card px-3 py-2 [scrollbar-width:none]">
              {SUGGESTIONS.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => sendMessage(s)}
                  className="press shrink-0 rounded-full border border-line bg-paper px-2.5 py-1 text-[11px] font-medium text-ink-mid hover:border-gold hover:bg-gold-soft hover:text-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="border-t border-line bg-card p-2.5"
          >
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Спросите об услугах, ценах, мастерах..."
                className="flex-1 rounded-xl border border-line bg-paper px-3.5 py-2 text-sm text-ink placeholder:text-ink-soft focus:border-primary focus:bg-card focus:outline-none"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                aria-label="Отправить"
                className="press flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-white shadow-sm hover:bg-primary-deep disabled:opacity-40"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="size-4 rotate-90">
                  <path d="M12 19V5" />
                  <path d="m5 12 7-7 7 7" />
                </svg>
              </button>
            </div>
            <div className="mt-1.5 flex items-center justify-between px-1 text-[9px] text-ink-soft">
              <span>Цепочка отказоустойчивости: Gemini ➔ Claude ➔ Codex</span>
              <span>NurCRM AI</span>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
