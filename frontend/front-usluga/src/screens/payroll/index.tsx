"use client";

import { useState } from "react";
import { Button, ConfirmButton, PageHeader, Segmented } from "@/components/ui";
import { useI18n } from "@/i18n/provider";
import { newId, useStore } from "@/data/store";
import { addMonths, fmtPeriod, periodOf, toIsoLocal, todayKey } from "@/lib/dates";
import { accrualsFor, closedOf } from "./use-accruals";
import { SchemesTab } from "./schemes";
import { PeriodTab } from "./period";
import { PayslipsTab } from "./payslips";
import { PayoutsTab } from "./payouts";
import { CabinetTab } from "./cabinet";
import { SimulatorTab } from "./simulator";

type Tab = "schemes" | "period" | "payslips" | "payouts" | "cabinet" | "simulator";

export function PayrollScreen() {
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const { db, update, role, userId, canManage } = useStore();
  const [tab, setTab] = useState<Tab>(role === "master" ? "cabinet" : "period");
  const [period, setPeriod] = useState(periodOf(todayKey()));
  const tabs: Tab[] = role === "master" ? ["cabinet", "payslips"] : ["period", "payslips", "payouts", "schemes", "cabinet", "simulator"];
  const withPeriod = tab === "period" || tab === "payslips" || tab === "payouts";
  const c = t.u.closing;
  const closed = closedOf(db, period);
  // Закрыть можно только прошедший месяц: текущий ещё идёт.
  const canClose = canManage("zarplata") && role !== "master" && period < periodOf(todayKey());
  const notApproved = db.staff.filter((s) => s.schemeId && s.active).filter((s) => {
    const slip = db.payslips.find((x) => x.staffId === s.id && x.period === period);
    return !slip || (slip.status !== "approved" && slip.status !== "paid");
  }).length;

  // Закрыть месяц: снимок начислений по всем филиалам, дальше они не пересчитываются.
  function closePeriod() {
    const now = toIsoLocal(new Date());
    update((d) => ({
      ...d,
      closedPeriods: [...d.closedPeriods.filter((x) => x.period !== period), { period, closedAt: now, closedById: userId, snapshot: accrualsFor(d, period, d.staff, true) }],
      audit: [{ id: newId("a"), at: now, staffId: userId, entity: "payslip", entityId: period, action: "update" as const, summary: `${c.close}: ${period}` }, ...d.audit],
    }));
  }
  function reopenPeriod() {
    const now = toIsoLocal(new Date());
    update((d) => ({
      ...d,
      closedPeriods: d.closedPeriods.filter((x) => x.period !== period),
      audit: [{ id: newId("a"), at: now, staffId: userId, entity: "payslip", entityId: period, action: "update" as const, summary: `${c.reopen}: ${period}` }, ...d.audit],
    }));
  }

  return (
    <div>
      <PageHeader
        title={p.title}
        subtitle={p.subtitle}
        actions={
          withPeriod ? (
            <>
              <Button size="sm" onClick={() => setPeriod(addMonths(period, -1))} aria-label={p.prevPeriod}>‹</Button>
              <span className="min-w-36 text-center text-sm font-semibold">{fmtPeriod(period, lang)}</span>
              <Button size="sm" onClick={() => setPeriod(addMonths(period, 1))} aria-label={p.nextPeriod}>›</Button>
            </>
          ) : undefined
        }
      />
      {withPeriod && role !== "master" && (
        closed ? (
          <div className="anim-rise mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-line bg-primary px-4 py-3 text-sm text-white">
            <span className="rounded-lg bg-gold px-2 py-0.5 text-xs font-extrabold text-primary">{c.closed}</span>
            <span className="min-w-0 flex-1">{closed.closedAt.slice(8, 10)}.{closed.closedAt.slice(5, 7)} {closed.closedAt.slice(11, 16)}, {c.by}: {db.staff.find((s) => s.id === closed.closedById)?.name ?? "—"}. {c.closedHint}</span>
            {role === "owner" && <ConfirmButton variant="secondary" onConfirm={reopenPeriod}>{c.reopen}</ConfirmButton>}
          </div>
        ) : canClose ? (
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-line bg-card px-4 py-3 text-sm">
            <span className="min-w-0 flex-1 text-ink-soft">{c.closeHint}{notApproved > 0 && <b className="ml-1 text-warn">· {c.notApproved}: {notApproved}</b>}</span>
            <ConfirmButton variant="primary" onConfirm={closePeriod}>{c.close}</ConfirmButton>
          </div>
        ) : null
      )}
      <div className="mb-5 overflow-x-auto">
        <Segmented value={tab} onChange={setTab} options={tabs.map((k) => ({ value: k, label: p.tabs[k] }))} />
      </div>
      <div key={tab} className="anim-fade-in">
        {tab === "schemes" && <SchemesTab />}
        {tab === "period" && <PeriodTab period={period} />}
        {tab === "payslips" && <PayslipsTab period={period} />}
        {tab === "payouts" && <PayoutsTab period={period} />}
        {tab === "cabinet" && <CabinetTab />}
        {tab === "simulator" && <SimulatorTab />}
      </div>
    </div>
  );
}
