"use client";

import type { ExplainStep } from "@/lib/payroll/calc";
import { useI18n } from "@/i18n/provider";
import { fmtMoney } from "@/lib/money";

// Расшифровка начисления словами: «Стрижка 1 500 → скидка −150 → материалы −50 → база 1 300 × 40 % = 520».
export function AccrualExplain({ steps }: { steps: ExplainStep[] }) {
  const { t } = useI18n();
  const e = t.u.explain;
  const parts: string[] = [];
  for (const s of steps) {
    switch (s.k) {
      case "price": parts.push(`${s.name}${s.qty > 1 ? ` × ${s.qty}` : ""} ${fmtMoney(s.v)}`); break;
      case "discount_master": parts.push(`${e.discountMaster} −${fmtMoney(s.v)}`); break;
      case "discount_salon": parts.push(`${e.discountSalon} (${fmtMoney(s.v)})`); break;
      case "materials": parts.push(`${e.materials} −${fmtMoney(s.v)}`); break;
      case "base": parts.push(`${e.base} ${fmtMoney(s.v)}`); break;
      case "rate": parts.push(s.mode === "percent" ? `× ${s.value}\u00a0%` : `${e.fixed} ${fmtMoney(s.value)}`); break;
      case "count": parts.push(`${s.v} ${e.count} (${e.from} ${s.min})`); break;
      case "revenue": parts.push(`${e.revenue} ${fmtMoney(s.v)}`); break;
      case "threshold": parts.push(`${e.threshold} ${fmtMoney(s.v)} ${s.ok ? e.reached : e.notReached}`); break;
      case "package": parts.push(e.package); break;
      case "share": parts.push(`${e.share} ${s.v}\u00a0%`); break;
      case "late": parts.push(`${e.late} ${s.v}`); break;
      case "shift": parts.push(`${e.shift} ${s.date.slice(8, 10)}.${s.date.slice(5, 7)}, ${s.hours} ${e.hours}`); break;
      case "amount": parts.push(`= ${fmtMoney(s.v)}`); break;
    }
  }
  return <span className="text-xs text-ink-soft">{parts.join(" → ").replace(" → = ", " = ")}</span>;
}
