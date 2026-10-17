"use client";

import { useState } from "react";
import { Button, ConfirmButton, Drawer, Field, Input, PageHeader, Segmented, Select } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Shift } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addMonths, daysInPeriod, fmtPeriod, parseIso, periodOf, todayKey } from "@/lib/dates";

export function ShiftsScreen() {
  const { db, update, branchId, role, userId, canManage } = useStore();
  const manage = canManage("smeny");
  const { t, lang } = useI18n();
  const u = t.u;
  const today = todayKey();
  const [period, setPeriod] = useState(periodOf(today));
  const [editing, setEditing] = useState<Shift | null>(null);
  const branch = branchId === "all" ? db.branches[0].id : branchId;
  const masters = db.staff.filter((s) => s.active && s.branchIds.includes(branch) && s.role !== "owner" && (role !== "master" || s.id === userId));
  const days = daysInPeriod(period);
  const closed = db.closedPeriods.some((c) => c.period === period);
  const shiftAt = (staffId: string, date: string) => db.shifts.find((s) => s.staffId === staffId && s.date === date && s.branchId === branch);

  function save() {
    if (!editing) return;
    update((d) => ({ ...d, shifts: d.shifts.some((s) => s.id === editing.id) ? d.shifts.map((s) => (s.id === editing.id ? editing : s)) : [...d.shifts, editing] }));
    setEditing(null);
  }
  function remove() {
    if (!editing) return;
    update((d) => ({ ...d, shifts: d.shifts.filter((s) => s.id !== editing.id) }));
    setEditing(null);
  }

  return (
    <div>
      <PageHeader title={u.shifts.title} subtitle={u.shifts.subtitle} actions={
        <>
          <Button size="sm" onClick={() => setPeriod(addMonths(period, -1))} aria-label={u.shifts.prevMonth}>‹</Button>
          <span className="min-w-36 text-center text-sm font-semibold">{fmtPeriod(period, lang)}</span>
          <Button size="sm" onClick={() => setPeriod(addMonths(period, 1))} aria-label={u.shifts.nextMonth}>›</Button>
        </>
      } />
      <p className="mb-3 text-xs text-ink-soft">{u.shifts.legend}. {u.timesheet.legend}</p>
      {closed && <p className="mb-3 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white">{u.closing.closed}. {u.closing.closedHint}</p>}
      <div className="overflow-x-auto rounded-xl border border-line bg-card">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-card px-3 py-2 text-left font-semibold">{u.staff.title}</th>
              {days.map((d) => {
                const dow = (parseIso(d).getDay() + 6) % 7;
                return <th key={d} className={`min-w-8 px-1 py-2 text-center font-semibold ${dow >= 5 ? "text-danger" : "text-ink-soft"} ${d === today ? "bg-primary/10" : ""}`}>{Number(d.slice(8))}</th>;
              })}
              <th className="px-3 py-2 text-right font-semibold text-ink-soft">{u.shifts.workedCount}</th>
              <th className="px-3 py-2 text-right font-semibold text-ink-soft">{u.timesheet.lateTotal}</th>
            </tr>
          </thead>
          <tbody>
            {masters.map((m) => {
              const count = days.filter((d) => { const s = shiftAt(m.id, d); return s && s.fact !== "missed"; }).length;
              const late = days.reduce((sum, d) => { const s = shiftAt(m.id, d); return sum + (s?.fact === "worked" ? (s.lateMin ?? 0) + (s.earlyMin ?? 0) : 0); }, 0);
              return (
                <tr key={m.id} className="border-t border-line">
                  <td className="sticky left-0 z-10 whitespace-nowrap bg-card px-3 py-1.5 font-semibold">
                    <span className="mr-2 inline-block size-2 rounded-full" style={{ background: m.color }} />{m.name.split(" ")[0]}
                  </td>
                  {days.map((d) => {
                    const s = shiftAt(m.id, d);
                    const away = s?.fact === "missed" ? s.absence ?? "absent" : null;
                    const cls = !s ? "hover:bg-paper" : away === "absent" ? "bg-danger/15 text-danger" : away ? "bg-gold-soft text-warn" : s.fact === "worked" ? "bg-positive-soft text-positive font-bold" : "bg-line/60 text-ink-soft";
                    const lateMark = s?.fact === "worked" && ((s.lateMin ?? 0) + (s.earlyMin ?? 0)) > 0;
                    return (
                      <td key={d} className={`p-0.5 ${d === today ? "bg-primary/5" : ""}`}>
                        <button type="button" aria-label={`${m.name} ${d}`} disabled={!manage || closed} onClick={() => manage && !closed && setEditing(s ?? { id: newId("sh"), staffId: m.id, branchId: branch, date: d, from: "10:00", to: "20:00", breakMin: 60, fact: d < today ? "worked" : "planned" })} className={`block h-7 w-full rounded ${cls} disabled:cursor-default`}>
                        {s ? (away ? u.timesheet.short[away] : `${s.from.slice(0, 2)}${lateMark ? "!" : ""}`) : ""}
                        </button>
                      </td>
                    );
                  })}
                  <td className="px-3 py-1.5 text-right tabular-nums">{count}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums ${late ? "text-warn" : "text-ink-soft"}`}>{late || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing ? `${u.shifts.shift}: ${db.staff.find((s) => s.id === editing.staffId)?.name}, ${editing.date.slice(8)}.${editing.date.slice(5, 7)}` : ""}
        footer={<>{editing && db.shifts.some((s) => s.id === editing.id) && <ConfirmButton onConfirm={remove}>{u.shifts.remove}</ConfirmButton>}<span className="flex-1" /><Button onClick={() => setEditing(null)}>{u.common.cancel}</Button><Button variant="primary" onClick={save}>{u.common.save}</Button></>}>
        {editing && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <Field label={u.shifts.from}><Input type="time" value={editing.from} onChange={(e) => setEditing({ ...editing, from: e.target.value })} /></Field>
              <Field label={u.shifts.to}><Input type="time" value={editing.to} onChange={(e) => setEditing({ ...editing, to: e.target.value })} /></Field>
              <Field label={u.shifts.breakMin}><Input type="number" min={0} step={15} value={editing.breakMin} onChange={(e) => setEditing({ ...editing, breakMin: Number(e.target.value) || 0 })} /></Field>
            </div>
            <Field label={u.shifts.fact}>
              <Segmented value={editing.fact} onChange={(f) => setEditing({ ...editing, fact: f, absence: f === "missed" ? editing.absence ?? "absent" : undefined })} options={[{ value: "planned", label: u.shifts.planned }, { value: "worked", label: u.shifts.worked }, { value: "missed", label: u.shifts.missed }]} />
            </Field>
            {editing.fact === "missed" && (
              <Field label={u.timesheet.absence}>
                <Select value={editing.absence ?? "absent"} onChange={(e) => setEditing({ ...editing, absence: e.target.value as NonNullable<Shift["absence"]> })}>
                  {(["absent", "vacation", "sick", "dayoff"] as const).map((k) => <option key={k} value={k}>{u.timesheet.absences[k]}</option>)}
                </Select>
              </Field>
            )}
            {editing.fact === "worked" && (
              <div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label={u.timesheet.lateMin}><Input type="number" min={0} step={5} value={editing.lateMin ?? 0} onChange={(e) => setEditing({ ...editing, lateMin: Math.max(0, Number(e.target.value) || 0) })} /></Field>
                  <Field label={u.timesheet.earlyMin}><Input type="number" min={0} step={5} value={editing.earlyMin ?? 0} onChange={(e) => setEditing({ ...editing, earlyMin: Math.max(0, Number(e.target.value) || 0) })} /></Field>
                </div>
                <p className="mt-1 text-xs text-ink-soft">{u.timesheet.lateHint}</p>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
