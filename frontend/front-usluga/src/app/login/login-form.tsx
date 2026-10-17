"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/i18n/provider";

type ErrorKey = "credentials" | "network" | "server" | null;

export function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });
      const data = (await res.json().catch(() => ({}))) as { next?: string; error?: string };
      if (res.ok && data.next) {
        router.replace(data.next);
        return;
      }
      setError(data.error === "credentials" || data.error === "network" ? data.error : "server");
    } catch {
      setError("network");
    } finally {
      setBusy(false);
    }
  }

  const errorText =
    error === "credentials" ? t.login.errorCredentials : error === "network" ? t.login.errorNetwork : error === "server" ? t.login.errorServer : null;

  return (
    <form onSubmit={onSubmit} className="w-full max-w-[420px] rounded-3xl bg-card p-8 shadow-[0_24px_60px_rgba(11,42,60,.12)]" noValidate>
      <h2 className="text-2xl font-bold tracking-tight">{t.login.submit}</h2>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">{t.login.lead}</p>

      <label className="mt-8 block">
        <span className="text-sm font-semibold">{t.login.loginLabel}</span>
        <input
          name="login"
          type="text"
          inputMode="email"
          autoComplete="username"
          required
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          className="mt-1.5 h-[50px] w-full rounded-xl border border-line-strong bg-card px-3.5 text-[15px] outline-none focus:border-primary"
        />
      </label>

      <label className="mt-4 block">
        <span className="text-sm font-semibold">{t.login.passwordLabel}</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1.5 h-[50px] w-full rounded-xl border border-line-strong bg-card px-3.5 text-[15px] outline-none focus:border-primary"
        />
      </label>

      {errorText && (
        <p role="alert" className="mt-4 rounded-lg border border-danger/30 bg-danger/5 px-3.5 py-2.5 text-sm text-danger">
          {errorText}
        </p>
      )}

      <button
        type="submit"
        disabled={busy || !login || !password}
        className="press mt-6 h-[52px] w-full rounded-[14px] bg-gold px-4 text-base font-extrabold text-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? t.login.submitting : t.login.submit}
      </button>
    </form>
  );
}
