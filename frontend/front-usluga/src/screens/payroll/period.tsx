"use client";

import { useState } from "react";
import { AccrualExplain } from "@/components/accrual-explain";
import { Badge, Button, Cell, Drawer, Field, Input, Row, Stat, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { AccrualSource } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, todayKey } from "@/lib/dates";
import { fmtMoney, pct } from "@/lib/money";
import { closedOf, periodRevenue, usePeriodAccruals } from "./use-accruals";
import { downloadCsv } from "@/lib/csv";

const SOURCES: AccrualSource[] = ["visit", "booking", "salary", "daily_bonus", "branch_share", "shift", "stepped", "refund", "adjustment"];

export function PeriodTab({ period }: { period: string }) {
  const { db, update, branchId, canManage } = useStore();
  const closed = !!closedOf(db, period);
  const manage = canManage("zarplata") && !closed;
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const accruals = usePeriodAccruals(period);
  const [open, setOpen] = useState<string | null>(null);
  const [adj, setAdj] = useState<{ amount: number; reason: string } | null>(null);

  const staffIds = Array.from(new Set([...db.staff.filter((s) => s.schemeId && s.active && (branchId === "all" || s.branchIds.includes(branchId))).map((s) => s.id), ...accruals.map((a) => a.staffId)]));
  const rows = staffIds.map((id) => {
    const mine = accruals.filter((a) => a.staffId === id);
    const by = Object.fromEntries(SOURCES.map((s) => [s, mine.filter((a) => a.source === s).reduce((sum, a) => sum + a.amount, 0)])) as Record<AccrualSource, number>;
    const total = mine.reduce((s, a) => s + a.amount, 0);
    const paid = db.payouts.filter((x) => x.staffId === id && x.period === period).reduce((s, x) => s + x.amount, 0);
    return { id, name: db.staff.find((s) => s.id === id)?.name ?? id, by, total, paid };
  }).sort((a, b) => b.total - a.total);
  const fot = rows.reduce((s, r) => s + r.total, 0);
  const revenue = periodRevenue(db, period, branchId);
  const fotPct = revenue ? (fot / revenue) * 100 : 0;
  const warn = fotPct > db.settings.fotThreshold;
  const visibleSources = SOURCES.filter((s) => rows.some((r) => r.by[s] !== 0));
  const current = open ? rows.find((r) => r.id === open) : null;
  const currentAcc = accruals.filter((a) => a.staffId === open).sort((a, b) => b.date.localeCompare(a.date));

  function exportCsv() {
    const out: (string | number)[][] = [[p.employee, ...visibleSources.map((s) => p.bySource[s]), p.accrued, p.paidOut, p.toPay]];
    for (const r of rows) out.push([r.name, ...visibleSources.map((s) => r.by[s]), r.total, r.paid, r.total - r.paid]);
    out.push([t.u.common.total, ...visibleSources.map((s) => rows.reduce((sum, r) => sum + r.by[s], 0)), fot, rows.reduce((s, r) => s + r.paid, 0), rows.reduce((s, r) => s + r.total - r.paid, 0)]);
    downloadCsv(`zarplata-${period}${branchId === "all" ? "" : "-" + branchId}`, out);
  }
  function saveAdj() {
    if (!open || !adj || !adj.amount || !adj.reason.trim()) return;
    update((d) => ({ ...d, adjustments: [...d.adjustments, { id: newId("adj"), staffId: open, date: todayKey().startsWith(period) ? todayKey() : `${period}-28`, amount: adj.amount, reason: adj.reason.trim() }] }));
    setAdj(null);
  }

  return (
    <div>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Stat label={p.revenue} value={fmtMoney(revenue)} />
        <Stat label={p.fot} value={fmtMoney(fot)} hint={`${pct(Math.round(fotPct * 10) / 10)} ${p.fotOfRevenue}${warn ? ` · ${p.fotWarn}` : ""}`} tone={warn ? "bad" : undefined} />
        <Stat label={p.toPay} value={fmtMoney(rows.reduce((s, r) => s + r.total - r.paid, 0))} />
      </div>
      <div className="mb-3 flex justify-end"><Button size="sm" onClick={exportCsv} disabled={rows.length === 0}>{p.exportCsv}</Button></div>
      <Table head={[p.employee, ...visibleSources.map((s) => p.bySource[s]), p.accrued, p.paidOut, p.toPay]} empty={t.u.common.nothing}>
        {rows.map((r) => (
          <Row key={r.id} onClick={() => setOpen(r.id)}>
            <Cell className="font-semibold">{r.name}</Cell>
            {visibleSources.map((s) => <Cell key={s} right className={r.by[s] < 0 ? "text-danger" : r.by[s] === 0 ? "text-ink-soft" : ""}>{r.by[s] ? fmtMoney(r.by[s]) : "—"}</Cell>)}
            <Cell right className="font-semibold">{fmtMoney(r.total)}</Cell>
            <Cell right className="text-ink-soft">{fmtMoney(r.paid)}</Cell>
            <Cell right className={`font-semibold ${r.total - r.paid < 0 ? "text-danger" : "text-primary"}`}>{fmtMoney(r.total - r.paid)}</Cell>
          </Row>
        ))}
      </Table>

      <Drawer open={!!open} onClose={() => { setOpen(null); setAdj(null); }} title={current ? `${current.name}: ${fmtMoney(current.total)}` : ""} wide
        footer={manage ? <><Button onClick={() => setAdj(adj ? null : { amount: 0, reason: "" })}>{p.addAdjustment}</Button></> : undefined}>
        {adj && (
          <div className="mb-4 grid gap-3 rounded-lg border border-line p-3 sm:grid-cols-[140px_1fr_auto]">
            <Field label={p.amount} hint={p.adjustmentAmountHint}><Input type="number" value={adj.amount || ""} onChange={(e) => setAdj({ ...adj, amount: Number(e.target.value) || 0 })} /></Field>
            <Field label={p.adjustmentReason}><Input value={adj.reason} onChange={(e) => setAdj({ ...adj, reason: e.target.value })} /></Field>
            <div className="self-end"><Button variant="primary" onClick={saveAdj} disabled={!adj.amount || !adj.reason.trim()}>{t.u.common.save}</Button></div>
          </div>
        )}
        <h3 className="mb-2 text-sm font-semibold">{p.accruals}</h3>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {currentAcc.map((a) => (
            <li key={a.id} className="px-3 py-2">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="flex items-center gap-2"><span className="text-xs text-ink-soft">{fmtDate(a.date, lang, { day: "numeric", month: "short" })}</span><Badge tone={a.amount < 0 ? "bad" : a.source === "visit" ? "neutral" : "info"}>{p.bySource[a.source]}</Badge></span>
                <span className={`tabular-nums font-semibold ${a.amount < 0 ? "text-danger" : ""}`}>{fmtMoney(a.amount)}</span>
              </div>
              <div className="mt-0.5">{a.source === "adjustment" ? <span className="text-xs text-ink-soft">{a.explanation}</span> : <AccrualExplain steps={a.steps} />}</div>
            </li>
          ))}
        </ul>
      </Drawer>
    </div>
  );
}
