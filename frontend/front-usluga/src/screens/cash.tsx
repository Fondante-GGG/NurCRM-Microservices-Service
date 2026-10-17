"use client";

import { useState } from "react";
import { Badge, Button, Card, Cell, ConfirmButton, Drawer, Field, Input, PageHeader, Row, Segmented, Select, Stat, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { CashOperation } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, periodOf, startOfWeek, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { downloadCsv } from "@/lib/csv";

export function CashScreen() {
  const { db, update, branchId, userId, role, canManage } = useStore();
  const manage = canManage("kassa");
  const { t } = useI18n();
  const u = t.u;
  const [period, setPeriod] = useState<"today" | "week" | "month">("today");
  const [editing, setEditing] = useState<CashOperation | null>(null);
  const today = todayKey();
  const branch = branchId === "all" ? db.branches[0].id : branchId;
  const registers = db.registers.filter((r) => r.branchId === branch);
  const allOps = db.cashOps.filter((o) => o.branchId === branch);
  // Неподтверждённые и отклонённые расходы не двигают остаток.
  const ops = allOps.filter((o) => !o.status || o.status === "approved");
  const pending = allOps.filter((o) => o.status === "pending").sort((a, b) => b.date.localeCompare(a.date));
  const a = u.approval;
  const limit = db.settings.approvalLimit;
  const needsApproval = (o: CashOperation) => o.kind === "out" && limit > 0 && o.amount > limit && role !== "owner";
  const closedDate = (iso: string) => db.closedPeriods.some((c) => c.period === iso.slice(0, 7));
  const inRange = (d: string) => (period === "today" ? d.startsWith(today) : period === "week" ? d.slice(0, 10) >= startOfWeek(today) : d.startsWith(periodOf(today)));
  const shown = allOps.filter((o) => inRange(o.date)).sort((a, b) => b.date.localeCompare(a.date));
  const counted = shown.filter((o) => !o.status || o.status === "approved");
  const sumIn = counted.filter((o) => o.kind === "in").reduce((s, o) => s + o.amount, 0);
  const sumOut = counted.filter((o) => o.kind === "out").reduce((s, o) => s + o.amount, 0);
  const balance = (rid: string) => ops.filter((o) => o.registerId === rid).reduce((s, o) => s + (o.kind === "in" ? o.amount : -o.amount), 0);
  const articles = Object.values(u.cash.articles);

  function save() {
    if (!editing || editing.amount <= 0 || closedDate(editing.date)) return;
    const op: CashOperation = needsApproval(editing) ? { ...editing, status: "pending" } : editing;
    update((d) => ({ ...d, cashOps: [...d.cashOps, op] }));
    setEditing(null);
  }
  function decide(o: CashOperation, ok: boolean) {
    update((d) => ({
      ...d,
      cashOps: d.cashOps.map((x) => (x.id === o.id ? { ...x, status: ok ? "approved" as const : "rejected" as const, approvedById: userId } : x)),
      audit: [{ id: newId("a"), at: toIsoLocal(new Date()), staffId: userId, entity: "cash", entityId: o.id, action: "update" as const, summary: `${ok ? a.approve : a.reject}: ${o.article} ${fmtMoney(o.amount)}` }, ...d.audit],
    }));
  }
  const stornoedIds = new Set(ops.map((o) => o.stornoOf).filter(Boolean));
  // Сторно: обратная операция той же суммы; исходная остаётся в журнале с пометкой.
  function storno(o: CashOperation) {
    update((d) => ({ ...d, cashOps: [...d.cashOps, { ...o, id: newId("co"), date: toIsoLocal(new Date()), kind: o.kind === "in" ? "out" : "in", staffId: userId, comment: `${u.cash.stornoOf} ${o.date.slice(0, 16).replace("T", " ")}${o.comment ? `: ${o.comment}` : ""}`, refType: null, refId: null, stornoOf: o.id }] }));
  }
  function exportCsv() {
    const rows: (string | number)[][] = [[u.common.date, u.cash.article, u.cash.income, u.cash.expense, u.cash.register, u.cash.who, u.cash.comment]];
    for (const o of counted) rows.push([o.date.replace("T", " "), o.article, o.kind === "in" ? o.amount : "", o.kind === "out" ? o.amount : "", db.registers.find((r) => r.id === o.registerId)?.name ?? "", db.staff.find((s) => s.id === o.staffId)?.name ?? "", o.comment]);
    rows.push([u.common.total, "", sumIn, sumOut, "", "", ""]);
    downloadCsv(`kassa-${period}-${today}`, rows);
  }

  return (
    <div>
      <PageHeader title={u.cash.title} subtitle={u.cash.subtitle} actions={<><Button onClick={exportCsv} disabled={shown.length === 0}>{u.cash.exportCsv}</Button>{manage && <Button variant="primary" onClick={() => setEditing({ id: newId("co"), branchId: branch, registerId: registers[0]?.id ?? "", date: toIsoLocal(new Date()), kind: "out", article: articles[5], amount: 0, staffId: userId, comment: "", refType: null, refId: null })}>{u.cash.newOperation}</Button>}</>} />
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {registers.map((r) => <Stat key={r.id} label={`${u.cash.register}: ${r.name}`} value={fmtMoney(balance(r.id))} hint={u.cash.balance} />)}
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Segmented value={period} onChange={setPeriod} options={[{ value: "today", label: u.cash.period.today }, { value: "week", label: u.cash.period.week }, { value: "month", label: u.cash.period.month }]} />
        <span className="text-sm text-ink-soft">{u.cash.todayIn}: <b className="text-ink">{fmtMoney(sumIn)}</b> · {u.cash.todayOut}: <b className="text-ink">{fmtMoney(sumOut)}</b> · {u.cash.todayNet}: <b className={sumIn - sumOut >= 0 ? "text-primary" : "text-danger"}>{fmtMoney(sumIn - sumOut)}</b></span>
      </div>
      {pending.length > 0 && (
        <Card className="anim-rise mb-4 border-gold p-4">
          <h2 className="font-bold">{a.title} · {pending.length}</h2>
          <p className="mt-0.5 text-xs text-ink-soft">{a.hint}</p>
          <ul className="mt-3 divide-y divide-line-soft">
            {pending.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className="text-xs text-ink-soft">{o.date.slice(8, 10)}.{o.date.slice(5, 7)} {o.date.slice(11, 16)}</span>
                <span className="font-semibold">{o.article}</span>
                <span className="min-w-0 flex-1 truncate text-ink-soft">{db.staff.find((s) => s.id === o.staffId)?.name}{o.comment ? ` · ${o.comment}` : ""}</span>
                <span className="tabular-nums font-bold text-danger">−{fmtMoney(o.amount)}</span>
                {role === "owner" ? (
                  <span className="flex gap-2"><Button size="sm" onClick={() => decide(o, false)}>{a.reject}</Button><Button size="sm" variant="primary" onClick={() => decide(o, true)}>{a.approve}</Button></span>
                ) : <Badge tone="warn">{a.pending}</Badge>}
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="mb-2 text-xs text-ink-soft">{u.cash.stornoHint}</p>
      <Table head={[u.common.date, u.cash.article, u.cash.register, u.cash.who, u.cash.comment, u.common.total, ""]} empty={u.common.nothing}>
        {shown.map((o) => (
          <Row key={o.id} className={stornoedIds.has(o.id) ? "opacity-60" : ""}>
            <Cell className="whitespace-nowrap">{o.date.slice(0, 10) === today ? o.date.slice(11) : `${o.date.slice(8, 10)}.${o.date.slice(5, 7)} ${o.date.slice(11)}`}</Cell>
            <Cell><Badge tone={o.stornoOf ? "warn" : o.kind === "in" ? "good" : "bad"}>{o.stornoOf ? u.cash.storno : o.article}</Badge>{stornoedIds.has(o.id) && <span className="ml-2 text-xs text-warn">{u.cash.stornoed}</span>}{o.status === "pending" && <span className="ml-2 text-xs font-semibold text-warn">{a.pending}</span>}{o.status === "rejected" && <span className="ml-2 text-xs font-semibold text-danger">{a.rejected}</span>}</Cell>
            <Cell className="text-ink-soft">{db.registers.find((r) => r.id === o.registerId)?.name}</Cell>
            <Cell className="text-ink-soft">{db.staff.find((s) => s.id === o.staffId)?.name ?? "—"}</Cell>
            <Cell className="text-ink-soft">{o.comment || (o.refType === "visit" ? `${db.clients.find((c) => c.id === db.visits.find((v) => v.id === o.refId)?.clientId)?.name ?? ""}` : "")}</Cell>
            <Cell right className={`${o.kind === "in" ? "" : "text-danger"} ${stornoedIds.has(o.id) || o.status === "rejected" ? "line-through" : ""} ${o.status === "pending" ? "opacity-60" : ""}`}>{o.kind === "in" ? "+" : "−"}{fmtMoney(o.amount)}</Cell>
            <Cell right>{manage && !o.refType && !o.stornoOf && !stornoedIds.has(o.id) && (!o.status || o.status === "approved") && <ConfirmButton variant="ghost" onConfirm={() => storno(o)}>{u.cash.storno}</ConfirmButton>}</Cell>
          </Row>
        ))}
      </Table>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={u.cash.newOperation} footer={<><Button onClick={() => setEditing(null)}>{u.common.cancel}</Button><Button variant="primary" onClick={save} disabled={!editing || editing.amount <= 0 || closedDate(editing.date)}>{u.common.save}</Button></>}>
        {editing && (
          <div className="space-y-4">
            <Segmented value={editing.kind} onChange={(k) => setEditing({ ...editing, kind: k })} options={[{ value: "in", label: u.cash.income }, { value: "out", label: u.cash.expense }]} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={u.cash.article}>
                <Select value={editing.article} onChange={(e) => setEditing({ ...editing, article: e.target.value })}>{articles.map((a) => <option key={a} value={a}>{a}</option>)}</Select>
              </Field>
              <Field label={u.cash.register}>
                <Select value={editing.registerId} onChange={(e) => setEditing({ ...editing, registerId: e.target.value })}>{registers.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>
              </Field>
              <Field label={u.common.total}><Input type="number" min={0} value={editing.amount || ""} onChange={(e) => setEditing({ ...editing, amount: Number(e.target.value) || 0 })} /></Field>
              <Field label={u.common.date}><Input type="date" value={editing.date.slice(0, 10)} onChange={(e) => e.target.value && setEditing({ ...editing, date: `${e.target.value}T${editing.date.slice(11)}` })} /></Field>
            </div>
            <Field label={u.cash.comment}><Input value={editing.comment} onChange={(e) => setEditing({ ...editing, comment: e.target.value })} /></Field>
            {needsApproval(editing) && <p className="rounded-lg bg-warn-soft px-3 py-2 text-xs font-semibold text-warn">{a.overLimit}</p>}
            {closedDate(editing.date) && <p className="rounded-lg bg-bad-soft px-3 py-2 text-xs font-semibold text-danger">{u.closing.dateClosed}</p>}
          </div>
        )}
      </Drawer>
      <span className="hidden">{addDays(today, 0)}</span>
    </div>
  );
}
