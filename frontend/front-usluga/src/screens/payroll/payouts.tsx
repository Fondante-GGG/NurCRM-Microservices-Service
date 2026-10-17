"use client";

import { useState } from "react";
import { Badge, Button, Cell, Drawer, Field, Input, Row, Select, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Payout } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { usePeriodAccruals } from "./use-accruals";

export function PayoutsTab({ period }: { period: string }) {
  const { db, update, branchId, userId, canManage } = useStore();
  const manage = canManage("zarplata");
  const { t, lang } = useI18n();
  const p = t.u.payroll;
  const accruals = usePeriodAccruals(period);
  const [editing, setEditing] = useState<Payout | null>(null);
  const staff = db.staff.filter((s) => s.schemeId && s.active && (branchId === "all" || s.branchIds.includes(branchId)));
  const list = db.payouts.filter((x) => x.period === period && staff.some((s) => s.id === x.staffId)).sort((a, b) => b.date.localeCompare(a.date));
  const balance = (id: string) => accruals.filter((a) => a.staffId === id).reduce((s, a) => s + a.amount, 0) - db.payouts.filter((x) => x.staffId === id && x.period === period).reduce((s, x) => s + x.amount, 0);

  function save() {
    if (!editing || editing.amount <= 0) return;
    update((d) => {
      const branch = d.staff.find((s) => s.id === editing.staffId)?.branchIds[0] ?? d.branches[0].id;
      return {
        ...d,
        payouts: [...d.payouts, editing],
        cashOps: [...d.cashOps, { id: newId("co"), branchId: branch, registerId: editing.registerId, date: `${editing.date}T${toIsoLocal(new Date()).slice(11)}`, kind: "out", article: "Зарплата", amount: editing.amount, staffId: userId, comment: `${d.staff.find((s) => s.id === editing.staffId)?.name}, ${editing.kind === "advance" ? p.advance : p.final}`, refType: "payout", refId: editing.id }],
      };
    });
    setEditing(null);
  }

  return (
    <div>
      {manage && <div className="mb-3 flex justify-end"><Button variant="primary" onClick={() => setEditing({ id: newId("po"), staffId: staff[0]?.id ?? "", period, amount: 0, date: todayKey(), registerId: db.registers[0]?.id ?? "", kind: "advance" })}>{p.newPayout}</Button></div>}
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {staff.map((s) => (
          <div key={s.id} className="flex items-center justify-between rounded-xl border border-line bg-card px-4 py-3 text-sm">
            <span className="font-semibold">{s.name}</span>
            <span className={`tabular-nums font-bold ${balance(s.id) > 0 ? "text-primary" : "text-ink-soft"}`}>{fmtMoney(balance(s.id))}</span>
          </div>
        ))}
      </div>
      <Table head={[t.u.common.date, p.employee, p.kind, t.u.cash.register, p.amount]} empty={t.u.common.nothing}>
        {list.map((x) => (
          <Row key={x.id}>
            <Cell>{fmtDate(x.date, lang, { day: "numeric", month: "short" })}</Cell>
            <Cell className="font-semibold">{db.staff.find((s) => s.id === x.staffId)?.name}</Cell>
            <Cell><Badge tone={x.kind === "advance" ? "warn" : "good"}>{x.kind === "advance" ? p.advance : p.final}</Badge></Cell>
            <Cell className="text-ink-soft">{db.registers.find((r) => r.id === x.registerId)?.name}</Cell>
            <Cell right className="font-semibold">{fmtMoney(x.amount)}</Cell>
          </Row>
        ))}
      </Table>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={p.newPayout} footer={<><Button onClick={() => setEditing(null)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={save} disabled={!editing || editing.amount <= 0}>{t.u.common.save}</Button></>}>
        {editing && (
          <div className="space-y-4">
            <Field label={p.employee}>
              <Select value={editing.staffId} onChange={(e) => setEditing({ ...editing, staffId: e.target.value })}>{staff.map((s) => <option key={s.id} value={s.id}>{s.name} · {fmtMoney(balance(s.id))}</option>)}</Select>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={p.kind}><Select value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value as Payout["kind"] })}><option value="advance">{p.advance}</option><option value="final">{p.final}</option></Select></Field>
              <Field label={p.amount}><Input type="number" min={0} value={editing.amount || ""} onChange={(e) => setEditing({ ...editing, amount: Number(e.target.value) || 0 })} /></Field>
              <Field label={t.u.common.date}><Input type="date" value={editing.date} onChange={(e) => e.target.value && setEditing({ ...editing, date: e.target.value })} /></Field>
              <Field label={t.u.cash.register}><Select value={editing.registerId} onChange={(e) => setEditing({ ...editing, registerId: e.target.value })}>{db.registers.map((r) => <option key={r.id} value={r.id}>{db.branches.find((b) => b.id === r.branchId)?.name} · {r.name}</option>)}</Select></Field>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
