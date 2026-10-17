"use client";

import { useI18n } from "@/i18n/provider";
import type { Lang } from "@/i18n/translations";

const LANGS: { code: Lang; label: string }[] = [
  { code: "ru", label: "Рус" },
  { code: "ky", label: "Кыр" },
];

export function LangSwitch({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div className={`inline-flex rounded-full border border-line-strong bg-card p-0.5 ${className}`} role="group" aria-label={t.shell.language}>
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          className={`rounded-full px-3 py-1 text-sm font-semibold transition-colors ${
            lang === l.code ? "bg-primary text-white" : "text-ink-mid hover:text-ink"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
