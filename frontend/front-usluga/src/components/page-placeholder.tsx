"use client";

import { useI18n } from "@/i18n/provider";

export function PagePlaceholder({ page }: { page: string }) {
  const { t } = useI18n();
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight">{t.menu[page]}</h1>
      <p className="mt-2 text-sm text-ink-soft">{t.shell.soon}</p>
    </div>
  );
}
