"use client";

import { useState } from "react";
import { AccrualExplain } from "@/components/accrual-explain";
import { Badge, Button, Cell, Drawer, Empty, Field, Input, Row, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Payslip, PayslipStatus } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { downloadCsv } from "@/lib/csv";
import { closedOf, usePeriodAccruals } from "./use-accruals";

const TONE: Record<PayslipStatus, "neutral" | "info" | "good" | "warn" | "bad"> = { draft: "neutral", review: "info", acknowledged: "good", disputed: "bad", approved: "good", paid: "good" };

export function PayslipsTab({ period }: { period: string }) {
  const { db, update, branchId, userId, role, canManage } = useStore();
  const manage = canManage("zarplata");
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const accruals = usePeriodAccruals(period);
  const [open, setOpen] = useState<string | null>(null);
  const [disputing, setDisputing] = useState<{ accrualId: string; comment: string } | null>(null);

  const staff = db.staff.filter((s) => s.schemeId && s.active && (branchId === "all" || s.branchIds.includes(branchId)) && (role !== "master" || s.id === userId));
  const slipOf = (staffId: string): Payslip => db.payslips.find((x) => x.staffId === staffId && x.period === period) ?? { id: `ps-${staffId}-${period}`, staffId, period, status: "draft", acknowledgedAt: null, disputes: [] };
  const totalOf = (staffId: string) => accruals.filter((a) => a.staffId === staffId).reduce((s, a) => s + a.amount, 0);
  const paidOf = (staffId: string) => db.payouts.filter((x) => x.staffId === staffId && x.period === period).reduce((s, x) => s + x.amount, 0);
  const payoutsOf = (staffId: string) => db.payouts.filter((x) => x.staffId === staffId && x.period === period).sort((a, b) => a.date.localeCompare(b.date));
  const advancesOf = (staffId: string) => payoutsOf(staffId).filter((x) => x.kind === "advance").reduce((s, x) => s + x.amount, 0);
  const bySourceOf = (staffId: string) => {
    const mine = accruals.filter((a) => a.staffId === staffId);
    const keys = Array.from(new Set(mine.map((a) => a.source)));
    return keys.map((k) => ({ source: k, amount: mine.filter((a) => a.source === k).reduce((s, a) => s + a.amount, 0) })).filter((x) => x.amount !== 0);
  };
  // Расчётный лист в Excel: начисления по видам, авансы, итог к выплате.
  function exportSlip(staffId: string) {
    const name = db.staff.find((s) => s.id === staffId)?.name ?? staffId;
    const rows: (string | number)[][] = [[p.payslip, name, period], []];
    for (const x of bySourceOf(staffId)) rows.push([p.bySource[x.source], x.amount]);
    rows.push([p.accrued, totalOf(staffId)], [p.advancesPaid, advancesOf(staffId)], [p.paidOut, paidOf(staffId)], [p.toPay, totalOf(staffId) - paidOf(staffId)], []);
    rows.push([t.u.common.date, p.kind, t.u.cash.register, p.amount]);
    for (const x of payoutsOf(staffId)) rows.push([x.date, x.kind === "advance" ? p.advance : p.final, db.registers.find((r) => r.id === x.registerId)?.name ?? "", x.amount]);
    downloadCsv(`vedomost-${period}-${name.split(" ")[0]}`, rows);
  }

  function setStatus(slip: Payslip, status: PayslipStatus) {
    const next: Payslip = { ...slip, status, acknowledgedAt: status === "acknowledged" ? toIsoLocal(new Date()) : slip.acknowledgedAt };
    update((d) => {
      let payouts = d.payouts;
      let cashOps = d.cashOps;
      if (status === "paid") {
        const due = totalOf(slip.staffId) - paidOf(slip.staffId);
        if (due > 0) {
          const branch = d.staff.find((s) => s.id === slip.staffId)?.branchIds[0] ?? d.branches[0].id;
          const reg = d.registers.find((r) => r.branchId === branch && r.kind === "cash")?.id ?? d.registers[0].id;
          payouts = [...payouts, { id: newId("po"), staffId: slip.staffId, period, amount: due, date: todayKey(), registerId: reg, kind: "final" }];
          cashOps = [...cashOps, { id: newId("co"), branchId: branch, registerId: reg, date: toIsoLocal(new Date()), kind: "out", article: "Зарплата", amount: due, staffId: userId, comment: `${d.staff.find((s) => s.id === slip.staffId)?.name}, ${period}`, refType: "payout", refId: slip.id }];
        }
      }
      return { ...d, payouts, cashOps, payslips: d.payslips.some((x) => x.id === next.id) ? d.payslips.map((x) => (x.id === next.id ? next : x)) : [...d.payslips, next] };
    });
  }
  function addDispute(slip: Payslip) {
    if (!disputing || !disputing.comment.trim()) return;
    const next: Payslip = { ...slip, status: "disputed", disputes: [...slip.disputes, { accrualId: disputing.accrualId, comment: disputing.comment.trim(), reply: "", status: "open" }] };
    update((d) => ({ ...d, payslips: d.payslips.some((x) => x.id === next.id) ? d.payslips.map((x) => (x.id === next.id ? next : x)) : [...d.payslips, next] }));
    setDisputing(null);
  }
  function resolve(slip: Payslip, i: number, reply: string) {
    const disputes = slip.disputes.map((x, j) => (j === i ? { ...x, reply, status: "resolved" as const } : x));
    const next: Payslip = { ...slip, disputes, status: disputes.every((x) => x.status === "resolved") ? "acknowledged" : "disputed" };
    update((d) => ({ ...d, payslips: d.payslips.map((x) => (x.id === next.id ? next : x)) }));
  }

  const closed = !!closedOf(db, period);
  const actions = (slip: Payslip) => {
    if (!manage && role !== "master") return null;
    // Закрытый месяц: можно только выплатить утверждённое.
    if (closed) return manage && slip.status === "approved" ? <Button size="sm" variant="primary" onClick={() => setStatus(slip, "paid")}>{p.markPaid}</Button> : null;
    if (role === "master") {
      return slip.status === "review" ? <Button size="sm" variant="primary" onClick={() => setStatus(slip, "acknowledged")}>{p.acknowledge}</Button> : null;
    }
    switch (slip.status) {
      case "draft": return <Button size="sm" onClick={() => setStatus(slip, "review")}>{p.toReview}</Button>;
      case "review": return <Button size="sm" onClick={() => setStatus(slip, "acknowledged")}>{p.acknowledge}</Button>;
      case "acknowledged": return <Button size="sm" variant="primary" onClick={() => setStatus(slip, "approved")}>{p.approve}</Button>;
      case "approved": return <Button size="sm" variant="primary" onClick={() => setStatus(slip, "paid")}>{p.markPaid}</Button>;
      default: return null;
    }
  };

  const current = open ? slipOf(open) : null;
  const currentAcc = accruals.filter((a) => a.staffId === open).sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div>
      <Table head={[p.employee, t.u.common.status, p.accrued, p.paidOut, p.toPay, ""]} empty={t.u.common.nothing}>
        {staff.map((s) => {
          const slip = slipOf(s.id);
          const total = totalOf(s.id), paid = paidOf(s.id);
          return (
            <Row key={s.id} onClick={() => setOpen(s.id)}>
              <Cell className="font-semibold">{s.name}</Cell>
              <Cell><Badge tone={TONE[slip.status]}>{p.statuses[slip.status]}</Badge>{slip.disputes.some((d) => d.status === "open") && <span className="ml-2 text-xs text-danger">{slip.disputes.filter((d) => d.status === "open").length}</span>}</Cell>
              <Cell right>{fmtMoney(total)}</Cell>
              <Cell right className="text-ink-soft">{fmtMoney(paid)}</Cell>
              <Cell right className="font-semibold">{fmtMoney(total - paid)}</Cell>
              <Cell right><span onClick={(e) => e.stopPropagation()}>{actions(slip)}</span></Cell>
            </Row>
          );
        })}
      </Table>

      <Drawer open={!!current} onClose={() => { setOpen(null); setDisputing(null); }} title={current ? `${p.payslip}: ${db.staff.find((s) => s.id === current.staffId)?.name}` : ""} wide
        footer={current && <><Badge tone={TONE[current.status]}>{p.statuses[current.status]}</Badge><span className="flex-1" /><Button size="sm" variant="ghost" onClick={() => exportSlip(current.staffId)}>{p.exportCsv}</Button>{actions(current)}</>}>
        {current && (
          <div className="space-y-5">
            <div className="rounded-xl border border-line">
              <div className="border-b border-line-soft px-3 py-2 text-sm font-semibold">{p.breakdown}</div>
              <ul className="divide-y divide-line-soft text-sm">
                {bySourceOf(current.staffId).map((x) => (
                  <li key={x.source} className="flex justify-between px-3 py-1.5"><span className="text-ink-soft">{p.bySource[x.source]}</span><span className={`tabular-nums ${x.amount < 0 ? "text-danger" : ""}`}>{fmtMoney(x.amount)}</span></li>
                ))}
                <li className="flex justify-between px-3 py-1.5 font-bold"><span>{p.accrued}</span><span className="tabular-nums">{fmtMoney(totalOf(current.staffId))}</span></li>
                <li className="flex justify-between px-3 py-1.5"><span className="text-ink-soft">{p.advancesPaid}</span><span className="tabular-nums">{fmtMoney(-advancesOf(current.staffId))}</span></li>
                <li className="flex justify-between px-3 py-1.5"><span className="text-ink-soft">{p.finalPaid}</span><span className="tabular-nums">{fmtMoney(advancesOf(current.staffId) - paidOf(current.staffId))}</span></li>
                <li className="flex justify-between bg-gold-soft px-3 py-2 font-extrabold"><span>{p.toPay}</span><span className="tabular-nums text-primary">{fmtMoney(totalOf(current.staffId) - paidOf(current.staffId))}</span></li>
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">{p.payoutsList}</h3>
              {payoutsOf(current.staffId).length === 0 ? <Empty text={p.noPayouts} /> : (
                <ul className="divide-y divide-line rounded-lg border border-line text-sm">
                  {payoutsOf(current.staffId).map((x) => (
                    <li key={x.id} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span className="flex items-center gap-2"><span className="text-xs text-ink-soft">{fmtDate(x.date, lang, { day: "numeric", month: "short" })}</span><Badge tone={x.kind === "advance" ? "warn" : "good"}>{x.kind === "advance" ? p.advance : p.final}</Badge><span className="text-xs text-ink-soft">{db.registers.find((r) => r.id === x.registerId)?.name}</span></span>
                      <span className="tabular-nums font-semibold">{fmtMoney(x.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">{p.disputes}</h3>
              {current.disputes.length === 0 ? <Empty text={p.noDisputes} /> : (
                <ul className="space-y-2">
                  {current.disputes.map((d, i) => {
                    const a = accruals.find((x) => x.id === d.accrualId);
                    return (
                      <li key={i} className={`rounded-lg border px-3 py-2 text-sm ${d.status === "open" ? "border-danger/40 bg-danger/5" : "border-line"}`}>
                        <div className="text-xs text-ink-soft">{a ? `${fmtDate(a.date, lang, { day: "numeric", month: "short" })} · ${a.explanation}` : d.accrualId}</div>
                        <div className="mt-1"><b>{p.disputeComment}:</b> {d.comment}</div>
                        {d.status === "resolved" ? <div className="mt-1 text-ink-soft"><b>{p.disputeReply}:</b> {d.reply}</div> : closed ? null : <ResolveForm onResolve={(reply) => resolve(current, i, reply)} />}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">{p.accruals}</h3>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {currentAcc.map((a) => (
                  <li key={a.id} className="px-3 py-2">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="flex items-center gap-2"><span className="text-xs text-ink-soft">{fmtDate(a.date, lang, { day: "numeric", month: "short" })}</span><Badge tone={a.amount < 0 ? "bad" : "neutral"}>{p.bySource[a.source]}</Badge></span>
                      <span className="flex items-center gap-3">
                        <span className={`tabular-nums font-semibold ${a.amount < 0 ? "text-danger" : ""}`}>{fmtMoney(a.amount)}</span>
                        {!closed && (current.status === "review" || current.status === "disputed") && !current.disputes.some((d) => d.accrualId === a.id) && <Button size="sm" variant="ghost" onClick={() => setDisputing({ accrualId: a.id, comment: "" })}>{p.dispute}</Button>}
                      </span>
                    </div>
                    <div className="mt-0.5">{a.source === "adjustment" ? <span className="text-xs text-ink-soft">{a.explanation}</span> : <AccrualExplain steps={a.steps} />}</div>
                    {disputing?.accrualId === a.id && (
                      <div className="mt-2 flex gap-2">
                        <Input placeholder={p.disputeComment} value={disputing.comment} onChange={(e) => setDisputing({ ...disputing, comment: e.target.value })} />
                        <Button size="sm" variant="primary" onClick={() => addDispute(current)} disabled={!disputing.comment.trim()}>{p.dispute}</Button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

function ResolveForm({ onResolve }: { onResolve: (reply: string) => void }) {
  const { t } = useI18n();
  const [reply, setReply] = useState("");
  return (
    <div className="mt-2 flex gap-2">
      <Field label=""><Input placeholder={t.u.payroll.disputeReply} value={reply} onChange={(e) => setReply(e.target.value)} /></Field>
      <div className="self-end"><Button size="sm" onClick={() => reply.trim() && onResolve(reply.trim())} disabled={!reply.trim()}>{t.u.payroll.resolve}</Button></div>
    </div>
  );
}
