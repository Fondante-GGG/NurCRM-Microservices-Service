"use client";

import { useI18n } from "@/i18n/provider";
import { SECTIONS } from "@/lib/sections";

export function RazdelPicker({ action }: { action: (formData: FormData) => Promise<void> }) {
  const { t } = useI18n();
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center px-4 py-10">
      <h1 className="text-2xl font-bold tracking-tight">{t.razdel.title}</h1>
      <p className="mt-2 text-sm text-ink-soft">{t.razdel.lead}</p>
      <form action={action} className="mt-8 grid gap-3 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <button
            key={s}
            name="section"
            value={s}
            className="rounded-xl border border-line bg-card p-5 text-left transition-colors hover:border-primary"
          >
            <div className="text-lg font-bold">{t.sections[s]}</div>
            <div className="mt-1 text-sm text-ink-soft">{t.sectionHints[s]}</div>
            <div className="mt-4 text-sm font-semibold text-primary">{t.razdel.open}</div>
          </button>
        ))}
      </form>
    </main>
  );
}
