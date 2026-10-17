"use client";

import { useMemo, useState } from "react";
import { Badge, Card, Cell, PageHeader, Row, Segmented, Stat, Table } from "@/components/ui";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { addDays, daysInPeriod, fmtDate, periodOf, startOfWeek, todayKey } from "@/lib/dates";
import { fmtMoney, pct } from "@/lib/money";
import { computeAccruals } from "@/lib/payroll/calc";
import { accrualsFor } from "./payroll/use-accruals";

export function AnalyticsScreen() {
  const { db, branchId, role, canManage } = useStore();
  // ФОТ, начисления и маржа: владельцу и тем, кто управляет зарплатой (бухгалтер).
  const money = role === "owner" || canManage("zarplata");
  const { t, lang } = useI18n();
  const a = t.u.analytics;
  const [range, setRange] = useState<"today" | "week" | "month">("month");
  const today = todayKey();
  const period = periodOf(today);
  const from = range === "today" ? today : range === "week" ? startOfWeek(today) : `${period}-01`;
  const inBranch = <T extends { branchId: string }>(x: T) => branchId === "all" || x.branchId === branchId;

  const visits = db.visits.filter((v) => inBranch(v) && v.closedAt.slice(0, 10) >= from && v.closedAt.slice(0, 10) <= today);
  const revenue = visits.reduce((s, v) => s + v.total - v.refundAmount, 0);
  const avg = visits.length ? revenue / visits.length : 0;
  const newClients = db.clients.filter((c) => c.createdAt >= from).length;

  const shifts = db.shifts.filter((s) => inBranch(s) && s.date >= from && s.date <= today && s.fact !== "missed");
  const shiftMin = shifts.reduce((s, x) => s + 600 - x.breakMin, 0);
  const busyMin = db.appointments.filter((x) => inBranch(x) && x.start.slice(0, 10) >= from && x.start.slice(0, 10) <= today && x.status !== "canceled" && x.status !== "no_show").reduce((s, x) => s + x.duration, 0);
  const load = shiftMin ? Math.min(100, Math.round((busyMin / shiftMin) * 100)) : 0;

  const accruals = useMemo(() => accrualsFor(db, period).filter((x) => branchId === "all" || x.branchId === branchId), [db, period, branchId]);
  const monthRevenue = db.visits.filter((v) => inBranch(v) && v.closedAt.startsWith(period)).reduce((s, v) => s + v.total - v.refundAmount, 0);
  const fot = accruals.reduce((s, x) => s + x.amount, 0);
  const fotPct = monthRevenue ? (fot / monthRevenue) * 100 : 0;
  const fotWarn = fotPct > db.settings.fotThreshold;

  const todayAppts = db.appointments.filter((x) => inBranch(x) && x.start.startsWith(today) && x.status !== "canceled");
  const count = (st: string[]) => todayAppts.filter((x) => st.includes(x.status)).length;

  const days = range === "today" ? [today] : range === "week" ? Array.from({ length: 7 }, (_, i) => addDays(from, i)).filter((d) => d <= today) : daysInPeriod(period).filter((d) => d <= today);
  const byDay = days.map((d) => ({ d, v: visits.filter((v) => v.closedAt.startsWith(d)).reduce((s, v) => s + v.total - v.refundAmount, 0) }));
  const maxDay = Math.max(1, ...byDay.map((x) => x.v));

  const masters = db.staff.filter((s) => s.role === "master" && s.active && (branchId === "all" || s.branchIds.includes(branchId))).map((m) => {
    const mv = visits.filter((v) => v.staffId === m.id);
    const rev = mv.reduce((s, v) => s + v.total - v.refundAmount, 0);
    const materials = mv.reduce((s, v) => s + v.lines.reduce((x, l) => x + l.materialsCost * l.qty, 0), 0);
    const pay = accruals.filter((x) => x.staffId === m.id && x.date >= from).reduce((s, x) => s + x.amount, 0);
    const clientIds = mv.map((v) => v.clientId);
    const repeat = clientIds.filter((id) => id && db.visits.some((v) => v.clientId === id && v.staffId === m.id && v.closedAt.slice(0, 10) < from)).length;
    return { m, visits: mv.length, rev, avg: mv.length ? rev / mv.length : 0, repeat: mv.length ? Math.round((repeat / mv.length) * 100) : 0, pay, margin: rev - materials - pay };
  }).sort((x, y) => y.rev - x.rev);

  const services = db.services.map((s) => {
    const lines = visits.flatMap((v) => v.lines.filter((l) => l.refId === s.id));
    const rev = lines.reduce((x, l) => x + l.price * l.qty - l.discount, 0);
    return { s, sold: lines.reduce((x, l) => x + l.qty, 0), rev };
  }).filter((x) => x.sold > 0).sort((x, y) => y.rev - x.rev);

  const sources = (["admin", "online", "bot"] as const).map((src) => ({ src, n: db.appointments.filter((x) => inBranch(x) && x.start.slice(0, 10) >= from && x.start.slice(0, 10) <= today && x.source === src).length }));
  const srcTotal = Math.max(1, sources.reduce((s, x) => s + x.n, 0));

  const returning = visits.filter((v) => v.clientId && db.visits.some((o) => o.clientId === v.clientId && o.closedAt.slice(0, 10) < from)).length;

  // Прогноз: факт месяца + стоящие записи, по той же схеме зарплаты.
  const forecast = useMemo(() => {
    const future = db.appointments.filter((x) => inBranch(x) && x.start > `${today}T23:59` && x.start.startsWith(period) && (x.status === "pending" || x.status === "confirmed"));
    const fVisits = future.map((ap) => {
      const pos = db.staff.find((s) => s.id === ap.staffId)?.positionId ?? "";
      const lines = ap.serviceIds.map((id) => { const s = db.services.find((x) => x.id === id)!; return { kind: s.addon ? "addon" as const : "service" as const, refId: s.id, name: s.name, price: s.pricesByPosition[pos] ?? s.price, qty: 1, discount: 0, discountAtExpense: s.discountAtExpense, materialsCost: s.materialsCost }; });
      const total = lines.reduce((s, l) => s + l.price, 0);
      return { id: `f-${ap.id}`, appointmentId: ap.id, branchId: ap.branchId, staffId: ap.staffId, clientId: ap.clientId, closedAt: ap.start, closedById: null, lines, tip: 0, tipChannel: "direct" as const, payment: { cash: total, card: 0, balance: 0 }, total, refundedAt: null, refundAmount: 0 };
    });
    const rev = monthRevenue + fVisits.reduce((s, v) => s + v.total, 0);
    const pay = computeAccruals({ period, staff: db.staff, schemes: db.schemes, services: db.services, visits: [...db.visits, ...fVisits], appointments: db.appointments, adjustments: db.adjustments, shifts: db.shifts }).filter((x) => branchId === "all" || x.branchId === branchId).reduce((s, x) => s + x.amount, 0);
    return { rev, pay };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, branchId, today, period, monthRevenue]);

  return (
    <div>
      <PageHeader title={a.title} subtitle={a.subtitle} actions={<Segmented value={range} onChange={setRange} options={[{ value: "today", label: a.period.today }, { value: "week", label: a.period.week }, { value: "month", label: a.period.month }]} />} />

      <Card className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3 text-sm">
        <span className="font-semibold">{a.todayJournal}: {todayAppts.length}</span>
        <span className="text-ink-soft">{count(["confirmed", "arrived", "paid"])} {a.confirmed}</span>
        <span className="text-ink-soft">{count(["arrived", "paid"])} {a.arrived}</span>
        <span className="text-ink-soft">{count(["no_show"])} {a.noShow}</span>
        <span className="text-ink-soft">{count(["pending"])} {a.pending}</span>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label={a.revenue} value={fmtMoney(revenue)} />
        <Stat label={a.visits} value={String(visits.length)} />
        <Stat label={a.avgCheck} value={fmtMoney(avg)} />
        <Stat label={a.newClients} value={String(newClients)} />
        <Stat label={a.load} value={pct(load)} />
        {money && <Stat label={a.fot} value={pct(Math.round(fotPct * 10) / 10)} hint={`${fmtMoney(fot)} ${a.ofRevenue}${fotWarn ? ` · ${a.fotWarn}` : ""}`} tone={fotWarn ? "bad" : "good"} />}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card className="p-4">
          <h3 className="text-sm font-semibold">{a.revenueByDay}</h3>
          <div className="mt-3 flex h-40 items-end gap-1">
            {byDay.map((x) => (
              <div key={x.d} className="group relative flex h-full flex-1 flex-col items-center justify-end" title={`${fmtDate(x.d, lang, { day: "numeric", month: "short" })}: ${fmtMoney(x.v)}`}>
                <div className="w-full rounded-t bg-primary/80 transition-[height] duration-500 group-hover:bg-primary" style={{ height: `${(x.v / maxDay) * 100}%` }} />
                {byDay.length <= 14 && <span className="mt-1 text-[10px] text-ink-soft">{Number(x.d.slice(8))}</span>}
              </div>
            ))}
          </div>
        </Card>
        <div className="grid gap-4">
          <Card className="p-4">
            <h3 className="text-sm font-semibold">{a.sources}</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {sources.map((x) => (
                <li key={x.src}>
                  <div className="flex justify-between"><span>{t.u.sources[x.src]}</span><span className="text-ink-soft">{x.n}</span></div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-paper"><div className="h-1.5 rounded-full bg-gold" style={{ width: `${(x.n / srcTotal) * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="p-4">
            <h3 className="text-sm font-semibold">{a.newVsReturning}</h3>
            <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-paper">
              <div className="bg-primary" style={{ width: `${visits.length ? (returning / visits.length) * 100 : 0}%` }} />
              <div className="bg-gold" style={{ width: `${visits.length ? ((visits.length - returning) / visits.length) * 100 : 0}%` }} />
            </div>
            <div className="mt-2 flex justify-between text-xs text-ink-soft"><span>{a.returning}: {returning}</span><span>{a.newOnes}: {visits.length - returning}</span></div>
          </Card>
        </div>
      </div>

      {money && <Card className="mt-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{a.forecast}</h3>
          <span className="text-xs text-ink-soft">{a.forecastHint}</span>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Stat label={a.forecastRevenue} value={fmtMoney(forecast.rev)} />
          <Stat label={a.forecastFot} value={fmtMoney(forecast.pay)} hint={`${pct(forecast.rev ? Math.round((forecast.pay / forecast.rev) * 1000) / 10 : 0)} ${a.ofRevenue}`} tone={forecast.rev && forecast.pay / forecast.rev * 100 > db.settings.fotThreshold ? "bad" : "good"} />
        </div>
      </Card>}

      <h3 className="mb-2 mt-6 text-sm font-semibold">{a.masters}</h3>
      <Table head={money ? [a.master, a.visits, a.revenue, a.avgCheck, a.repeat, a.accrued, a.margin] : [a.master, a.visits, a.revenue, a.avgCheck, a.repeat]} empty={t.u.common.nothing}>
        {masters.map((x) => (
          <Row key={x.m.id}>
            <Cell className="font-semibold"><span className="mr-2 inline-block size-2.5 rounded-full" style={{ background: x.m.color }} />{x.m.name}</Cell>
            <Cell right>{x.visits}</Cell>
            <Cell right>{fmtMoney(x.rev)}</Cell>
            <Cell right>{fmtMoney(x.avg)}</Cell>
            <Cell right>{pct(x.repeat)}</Cell>
            {money && <Cell right>{fmtMoney(x.pay)}</Cell>}
            {money && <Cell right className={x.margin < 0 ? "text-danger" : "text-primary"} title={a.marginHint}>{fmtMoney(x.margin)}</Cell>}
          </Row>
        ))}
      </Table>

      <h3 className="mb-2 mt-6 text-sm font-semibold">{a.services}</h3>
      <Table head={[t.u.common.name, a.sold, a.revenue, a.share]} empty={t.u.common.nothing}>
        {services.map((x) => (
          <Row key={x.s.id}>
            <Cell className="font-semibold">{x.s.name}{x.s.addon && <Badge>+</Badge>}</Cell>
            <Cell right>{x.sold}</Cell>
            <Cell right>{fmtMoney(x.rev)}</Cell>
            <Cell right>{pct(revenue ? Math.round((x.rev / revenue) * 1000) / 10 : 0)}</Cell>
          </Row>
        ))}
      </Table>
    </div>
  );
}
