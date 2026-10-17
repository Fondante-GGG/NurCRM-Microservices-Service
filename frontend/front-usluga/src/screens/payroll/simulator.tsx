"use client";

import { useMemo, useState } from "react";
import { Button, Card, Cell, Field, Input, Row, Select, Stat, Table } from "@/components/ui";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { addMonths, fmtPeriod, periodOf, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { accrualsFor } from "./use-accruals";

// Симулятор «что если»: сотрудников схемы A считаем по схеме B на фактических визитах прошлых месяцев.
export function SimulatorTab() {
  const { db } = useStore();
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const [fromScheme, setFromScheme] = useState(db.schemes[0]?.id ?? "");
  const [toScheme, setToScheme] = useState(db.schemes[1]?.id ?? db.schemes[0]?.id ?? "");
  const [months, setMonths] = useState(2);
  const [result, setResult] = useState<{ periods: string[]; rows: { name: string; before: number; after: number }[] } | null>(null);
  const [offerRevenue, setOfferRevenue] = useState(120000);
  const [offerScheme, setOfferScheme] = useState(db.schemes[0]?.id ?? "");

  function run() {
    const cur = periodOf(todayKey());
    const periods = Array.from({ length: months }, (_, i) => addMonths(cur, -(i + 1))).reverse();
    const people = db.staff.filter((s) => s.schemeId === fromScheme && s.active);
    const swapped = db.staff.map((s) => (s.schemeId === fromScheme ? { ...s, schemeId: toScheme } : s));
    const rows = people.map((s) => {
      let before = 0, after = 0;
      for (const per of periods) {
        before += accrualsFor(db, per, db.staff, true).filter((a) => a.staffId === s.id).reduce((x, a) => x + a.amount, 0);
        after += accrualsFor(db, per, swapped, true).filter((a) => a.staffId === s.id).reduce((x, a) => x + a.amount, 0);
      }
      return { name: s.name, before, after };
    });
    setResult({ periods, rows });
  }

  const totals = result ? result.rows.reduce((acc, r) => ({ before: acc.before + r.before, after: acc.after + r.after }), { before: 0, after: 0 }) : null;

  const offer = useMemo(() => {
    const s = db.schemes.find((x) => x.id === offerScheme);
    if (!s) return 0;
    let sum = 0;
    for (const c of s.components) {
      if (c.kind === "service_rate" && c.mode === "percent") sum += (offerRevenue * c.value) / 100;
      if (c.kind === "monthly_salary") sum += c.amount;
    }
    return sum;
  }, [db.schemes, offerScheme, offerRevenue]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div>
        <Card className="p-4">
          <h3 className="text-sm font-semibold">{p.simulator}</h3>
          <p className="mt-1 text-xs text-ink-soft">{p.simulatorHint}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <Field label={p.staffOnScheme}><Select value={fromScheme} onChange={(e) => setFromScheme(e.target.value)}>{db.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
            <Field label={p.candidate}><Select value={toScheme} onChange={(e) => setToScheme(e.target.value)}>{db.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
            <Field label={p.months}><Input type="number" min={1} max={6} value={months} onChange={(e) => setMonths(Math.min(6, Math.max(1, Number(e.target.value) || 1)))} /></Field>
          </div>
          <Button variant="primary" className="mt-3" onClick={run}>{p.run}</Button>
        </Card>
        {result && totals && (
          <div className="anim-rise mt-4">
            <p className="mb-2 text-xs text-ink-soft">{result.periods.map((x) => fmtPeriod(x, lang)).join(", ")}</p>
            <Table head={[p.employee, p.before, p.after, p.diff]} empty={p.nobody}>
              {result.rows.map((r) => (
                <Row key={r.name}>
                  <Cell className="font-semibold">{r.name}</Cell>
                  <Cell right>{fmtMoney(r.before)}</Cell>
                  <Cell right>{fmtMoney(r.after)}</Cell>
                  <Cell right className={r.after - r.before > 0 ? "text-danger" : "text-primary"}>{r.after - r.before > 0 ? "+" : ""}{fmtMoney(r.after - r.before)}</Cell>
                </Row>
              ))}
            </Table>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Stat label={p.before} value={fmtMoney(totals.before)} />
              <Stat label={p.after} value={fmtMoney(totals.after)} />
              <Stat label={p.fotDelta} value={`${totals.after - totals.before > 0 ? "+" : ""}${fmtMoney(totals.after - totals.before)}`} tone={totals.after - totals.before > 0 ? "bad" : "good"} />
            </div>
          </div>
        )}
      </div>
      <Card className="h-fit p-4">
        <h3 className="text-sm font-semibold">{p.offerCalc}</h3>
        <p className="mt-1 text-xs text-ink-soft">{p.offerHint}</p>
        <div className="mt-3 space-y-3">
          <Field label={p.scheme}><Select value={offerScheme} onChange={(e) => setOfferScheme(e.target.value)}>{db.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label={p.offerRevenue}><Input type="number" min={0} step={5000} value={offerRevenue} onChange={(e) => setOfferRevenue(Number(e.target.value) || 0)} /></Field>
          <div className="rounded-lg bg-paper p-3"><div className="text-xs text-ink-soft">{p.offerResult}</div><div className="text-2xl font-bold text-primary">{fmtMoney(offer)}</div></div>
        </div>
      </Card>
    </div>
  );
}
