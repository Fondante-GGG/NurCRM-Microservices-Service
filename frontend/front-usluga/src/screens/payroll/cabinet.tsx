"use client";

import { useMemo, useState } from "react";
import { AccrualExplain } from "@/components/accrual-explain";
import { Badge, Card, Field, Select, Stat } from "@/components/ui";
import { useStore } from "@/data/store";
import type { Visit } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, periodOf, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { computeAccruals } from "@/lib/payroll/calc";
import { accrualsFor } from "./use-accruals";

// Кабинет мастера: что заработал сегодня и за месяц, прогноз, лента с расшифровкой.
export function CabinetTab() {
  const { db, role, userId } = useStore();
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const masters = db.staff.filter((s) => s.role === "master" && s.active && s.schemeId && (role !== "master" || s.id === userId));
  const [staffId, setStaffId] = useState(masters[0]?.id ?? "");
  const today = todayKey();
  const period = periodOf(today);
  const me = db.staff.find((s) => s.id === staffId);

  const mine = useMemo(() => accrualsFor(db, period).filter((a) => a.staffId === staffId), [db, period, staffId]);
  const todaySum = mine.filter((a) => a.date === today).reduce((s, a) => s + a.amount, 0);
  const monthSum = mine.reduce((s, a) => s + a.amount, 0);

  // Прогноз: будущие записи месяца превращаем в условные визиты и считаем по той же схеме.
  const forecast = useMemo(() => {
    const future = db.appointments.filter((a) => a.staffId === staffId && a.start > `${today}T23:59` && a.start.startsWith(period) && (a.status === "pending" || a.status === "confirmed"));
    const pos = me?.positionId ?? "";
    const visits: Visit[] = future.map((a) => {
      const lines = (a.serviceIds || []).map((id) => {
        const s = (db.services || []).find((x) => x.id === id);
        if (!s) {
          return { kind: "service" as const, refId: id, name: "Услуга", price: 0, qty: 1, discount: 0, discountAtExpense: "salon" as const, materialsCost: 0 };
        }
        const prices = s.pricesByPosition || {};
        return {
          kind: s.addon ? ("addon" as const) : ("service" as const),
          refId: s.id,
          name: s.name,
          price: prices[pos] ?? s.price ?? 0,
          qty: 1,
          discount: 0,
          discountAtExpense: s.discountAtExpense || "salon",
          materialsCost: s.materialsCost || 0,
        };
      });
      const total = lines.reduce((s, l) => s + l.price, 0);
      return { id: `f-${a.id}`, appointmentId: a.id, branchId: a.branchId, staffId, clientId: a.clientId, closedAt: a.start, closedById: null, lines, tip: 0, tipChannel: "direct" as const, payment: { cash: total, card: 0, balance: 0 }, total, refundedAt: null, refundAmount: 0 };
    });
    return computeAccruals({
      period,
      staff: (db.staff || []).filter((s) => s.id === staffId),
      schemes: db.schemes || [],
      services: db.services || [],
      visits: [...(db.visits || []).filter((v) => v.staffId === staffId), ...visits],
      appointments: db.appointments || [],
      adjustments: db.adjustments || [],
      shifts: db.shifts || [],
    }).reduce((s, a) => s + (a.amount || 0), 0);
  }, [db, staffId, today, period, me]);

  const scheme = db.schemes.find((s) => s.id === me?.schemeId);
  const tiers = scheme?.components.find((c) => c.kind === "daily_count_bonus");
  const todayCount = db.visits.filter((v) => v.staffId === staffId && v.closedAt.startsWith(today) && !v.refundedAt).length;
  const nextTier = tiers && tiers.kind === "daily_count_bonus" ? [...tiers.tiers].sort((a, b) => a.minCount - b.minCount).find((x) => x.minCount > todayCount) : null;
  const reached = tiers && tiers.kind === "daily_count_bonus" ? [...tiers.tiers].sort((a, b) => b.minCount - a.minCount).find((x) => todayCount >= x.minCount) : null;
  const feed = [...mine].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 40);

  return (
    <div>
      {role !== "master" && <div className="mb-4 max-w-xs"><Field label={p.viewAs}><Select value={staffId} onChange={(e) => setStaffId(e.target.value)}>{masters.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field></div>}
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={p.todayEarned} value={fmtMoney(todaySum)} tone="good" />
        <Stat label={p.monthEarned} value={fmtMoney(monthSum)} />
        <Stat label={p.forecast} value={fmtMoney(forecast)} hint={p.forecastHint} />
      </div>
      {tiers && tiers.kind === "daily_count_bonus" && (
        <Card className="mt-4 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold">{reached ? `${p.tierReached}: ${reached.percent}\u00a0%` : p.tierProgress}</span>
            <span className="text-ink-soft">{todayCount} / {nextTier ? nextTier.minCount : reached?.minCount}</span>
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-paper">
            <div className="h-2 rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.min(100, (todayCount / (nextTier ? nextTier.minCount : Math.max(1, reached?.minCount ?? 1))) * 100)}%` }} />
          </div>
          {nextTier && <p className="mt-1 text-xs text-ink-soft">{p.tierLeft.replace("{n}", String(nextTier.minCount - todayCount)).replace("{p}", String(nextTier.percent))}</p>}
        </Card>
      )}
      <h3 className="mb-2 mt-6 text-sm font-semibold">{p.feed}</h3>
      <ul className="divide-y divide-line rounded-xl border border-line bg-card">
        {feed.map((a) => (
          <li key={a.id} className="px-4 py-2.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2"><span className="text-xs text-ink-soft">{fmtDate(a.date, lang, { day: "numeric", month: "short" })}</span><Badge tone={a.amount < 0 ? "bad" : a.source === "visit" ? "neutral" : "info"}>{p.bySource[a.source]}</Badge></span>
              <span className={`tabular-nums font-semibold ${a.amount < 0 ? "text-danger" : ""}`}>{fmtMoney(a.amount)}</span>
            </div>
            <div className="mt-0.5">{a.source === "adjustment" ? <span className="text-xs text-ink-soft">{a.explanation}</span> : <AccrualExplain steps={a.steps} />}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
