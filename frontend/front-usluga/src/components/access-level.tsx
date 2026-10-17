"use client";

import type { AccessLevel } from "@/data/types";
import { useI18n } from "@/i18n/provider";

// Переключатель уровня доступа к разделу: нет / просмотр / управление.
// compact: короткие подписи для широкой таблицы ролей; полная подпись остаётся в подсказке.
export function AccessLevelPicker({ value, onChange, disabled, label, compact }: { value: AccessLevel | null; onChange: (v: AccessLevel | null) => void; disabled?: boolean; label: string; compact?: boolean }) {
  const { t } = useI18n();
  const a = t.u.access;
  const opts: { v: AccessLevel | null; text: string; full: string }[] = [
    { v: null, text: a.levelNone, full: a.levelNone },
    { v: "view", text: compact ? a.levelViewShort : a.levelView, full: a.levelView },
    { v: "manage", text: compact ? a.levelManageShort : a.levelManage, full: a.levelManage },
  ];
  return (
    <div role="radiogroup" aria-label={label} className={`inline-flex rounded-[10px] bg-segment p-0.5 ${disabled ? "opacity-60" : ""}`}>
      {opts.map((o) => (
        <button key={String(o.v)} type="button" role="radio" title={o.full} aria-label={o.full} aria-checked={value === o.v} disabled={disabled} onClick={() => onChange(o.v)}
          className={`press whitespace-nowrap rounded-lg ${compact ? "px-2" : "px-2.5"} py-1 text-xs font-bold ${value === o.v ? (o.v === "manage" ? "bg-gold text-primary" : o.v === "view" ? "bg-card text-primary shadow-[0_1px_2px_rgba(16,24,40,.08)]" : "bg-card text-ink-soft shadow-[0_1px_2px_rgba(16,24,40,.08)]") : "text-[#475467]"}`}>
          {o.text}
        </button>
      ))}
    </div>
  );
}
