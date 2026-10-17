"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, Drawer, Field, Input, PageHeader, Select } from "@/components/ui";
import { Icon } from "@/components/icon";
import { newId, useStore } from "@/data/store";
import type { Appointment, Client } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

function minutesSince(iso: string): number {
  const [d, tm] = iso.split("T");
  const [y, m, dd] = d.split("-").map(Number);
  const [h, mi] = tm.split(":").map(Number);
  return Math.max(0, Math.round((Date.now() - new Date(y, m - 1, dd, h, mi).getTime()) / 60000));
}

// Поток: живая очередь без слотов (процедурный кабинет). Записи те же, что в журнале: pending = в очереди,
// arrived = принимают, paid = принят. «Занят» — флаг у сотрудника на сегодня.
export function FlowScreen() {
  const { db, update, branchId, userId, role, canManage } = useStore();
  const manage = canManage("zapisi");
  const { t } = useI18n();
  const f = t.u.flow;
  const router = useRouter();
  const today = todayKey();
  const branch = branchId === "all" ? db.branches[0].id : branchId;
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<{ clientId: string; name: string; phone: string; serviceIds: string[]; staffId: string }>({ clientId: "", name: "", phone: "", serviceIds: [], staffId: "" });
  const [q, setQ] = useState("");

  const nurses = db.staff.filter((s) => s.role === "master" && s.active && s.branchIds.includes(branch) && (role !== "master" || s.id === userId));
  const todays = db.appointments.filter((a) => a.branchId === branch && a.start.startsWith(today) && a.status !== "canceled" && a.status !== "no_show");
  const queue = todays.filter((a) => a.status === "pending" || a.status === "confirmed").sort((a, b) => a.start.localeCompare(b.start));
  const inService = todays.filter((a) => a.status === "arrived");
  const done = todays.filter((a) => a.status === "paid");
  const busyIds = useMemo(() => new Set(db.shifts.filter((s) => s.date === today && s.fact === "missed").map((s) => s.staffId)), [db.shifts, today]);
  const clientName = (id: string) => db.clients.find((c) => c.id === id)?.name ?? "—";
  const svcNames = (ids: string[]) => ids.map((id) => db.services.find((s) => s.id === id)?.name).join(", ");
  const found = q.trim().length >= 2 ? db.clients.filter((c) => (c.name + c.phone).toLowerCase().includes(q.toLowerCase())).slice(0, 5) : [];

  async function setBusy(staffId: string, busy: boolean) {
    try {
      await fetch(`/api/proxy/api/main/shifts/${staffId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fact: busy ? "busy" : "worked" }),
      });
    } catch {}
    update((d) => {
      const sh = d.shifts.find((s) => s.staffId === staffId && s.date === today);
      const shifts = sh ? d.shifts.map((s) => (s.id === sh.id ? { ...s, fact: busy ? "missed" as const : "worked" as const } : s)) : [...d.shifts, { id: newId("sh"), staffId, branchId: branch, date: today, from: "09:00", to: "21:00", breakMin: 0, fact: busy ? "missed" as const : "worked" as const }];
      return { ...d, shifts };
    });
  }
  async function take(a: Appointment, staffId?: string) {
    const sid = staffId ?? a.staffId;
    if (!sid) return;
    try {
      await fetch(`/api/proxy/api/main/appointments/${a.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "arrived", staff_id: sid }),
      });
    } catch {}
    update((d) => ({ ...d, appointments: d.appointments.map((x) => (x.id === a.id ? { ...x, status: "arrived", staffId: sid, start: toIsoLocal(new Date()) } : x)) }));
  }
  async function add() {
    if (!draft.serviceIds.length || (!draft.clientId && !draft.name.trim())) return;
    const duration = draft.serviceIds.reduce((s, id) => s + (db.services.find((x) => x.id === id)?.duration ?? 0), 0);
    const nowIso = toIsoLocal(new Date());
    let clientId = draft.clientId;
    if (!clientId) {
      const c: Client = { id: newId("cl"), name: draft.name.trim(), phone: draft.phone.trim(), birthday: null, category: "new", notes: "", consent: true, createdAt: today };
      clientId = c.id;
      update((d) => ({ ...d, clients: [...d.clients, c] }));
    }
    try {
      await fetch("/api/proxy/api/main/appointments/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          branch_id: branch,
          staff_id: draft.staffId || undefined,
          service_ids: draft.serviceIds,
          start: nowIso,
          duration,
          status: "pending",
        }),
      });
    } catch {}
    update((d) => ({
      ...d,
      appointments: [...d.appointments, { id: newId("ap"), branchId: branch, staffId: draft.staffId, clientId, start: nowIso, duration, serviceIds: draft.serviceIds, status: "pending", source: "admin", createdById: userId, note: "", visitId: null }]
    }));
    setAdding(false);
    setDraft({ clientId: "", name: "", phone: "", serviceIds: [], staffId: "" });
    setQ("");
  }
  const freeNurse = () => nurses.find((n) => !busyIds.has(n.id) && !inService.some((a) => a.staffId === n.id))?.id;

  return (
    <div>
      <PageHeader title={f.title} subtitle={f.subtitle} actions={manage ? <Button variant="primary" onClick={() => setAdding(true)}>{f.addToQueue}</Button> : undefined} />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {nurses.map((n) => {
          const busy = busyIds.has(n.id);
          const cur = inService.find((a) => a.staffId === n.id);
          return (
            <Card key={n.id} className="p-4">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-full text-sm font-extrabold text-white" style={{ background: n.color }}>{n.name.split(" ").map((w) => w[0]).slice(0, 2).join("")}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-bold">{n.name}</div>
                  <div className="text-xs">{busy ? <Badge tone="bad">{f.busy}</Badge> : cur ? <Badge tone="info">{clientName(cur.clientId)}</Badge> : <Badge tone="good">{f.free}</Badge>}</div>
                </div>
              </div>
              {(manage || n.id === userId) && (
                <Button size="sm" className="mt-3 w-full" variant={busy ? "primary" : "secondary"} onClick={() => setBusy(n.id, !busy)}>{busy ? f.markFree : f.markBusy}</Button>
              )}
            </Card>
          );
        })}
      </div>
      <p className="mb-4 text-xs text-ink-soft">{f.busyHint}</p>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4">
          <h2 className="font-bold">{f.queue} · {queue.length}</h2>
          <ul className="mt-3 space-y-2">
            {queue.length === 0 && <li className="rounded-xl border border-dashed border-line px-3 py-6 text-center text-sm text-ink-soft">{f.noQueue}</li>}
            {queue.map((a, i) => (
              <li key={a.id} className="rounded-xl border border-line px-3 py-2.5 text-sm">
                <div className="flex items-center justify-between gap-2"><span className="font-bold">{i + 1}. {clientName(a.clientId)}</span><span className="text-xs text-ink-soft">{f.waiting} {minutesSince(a.start)} {f.min}</span></div>
                <div className="text-xs text-ink-soft">{svcNames(a.serviceIds)}{a.staffId ? ` · ${db.staff.find((s) => s.id === a.staffId)?.name.split(" ")[0]}` : ""}</div>
                {manage && <Button size="sm" variant="primary" className="mt-2" onClick={() => take(a, a.staffId || freeNurse())} disabled={!a.staffId && !freeNurse()}>{f.take}</Button>}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-4">
          <h2 className="font-bold">{f.inService} · {inService.length}</h2>
          <ul className="mt-3 space-y-2">
            {inService.map((a) => (
              <li key={a.id} className="rounded-xl border border-gold bg-gold-soft px-3 py-2.5 text-sm">
                <div className="font-bold">{clientName(a.clientId)}</div>
                <div className="text-xs text-ink-soft">{svcNames(a.serviceIds)} · {db.staff.find((s) => s.id === a.staffId)?.name}</div>
                {manage && <Button size="sm" variant="primary" className="mt-2" onClick={() => router.push(`/usluga/prodazha?appointment=${a.id}`)}>{f.finish}</Button>}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-4">
          <h2 className="font-bold">{f.doneToday} · {done.length}</h2>
          <ul className="mt-3 max-h-96 space-y-1 overflow-y-auto text-sm">
            {done.slice().reverse().map((a) => {
              const v = db.visits.find((x) => x.id === a.visitId);
              return <li key={a.id} className="flex justify-between gap-2 border-b border-line-soft py-1.5"><span>{clientName(a.clientId)} <span className="text-xs text-ink-soft">{svcNames(a.serviceIds)}</span></span><span className="tabular-nums font-semibold">{v ? fmtMoney(v.total) : ""}</span></li>;
            })}
          </ul>
        </Card>
      </div>

      <Drawer open={adding} onClose={() => setAdding(false)} title={f.addToQueue} footer={<><Button onClick={() => setAdding(false)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={add} disabled={!draft.serviceIds.length || (!draft.clientId && !draft.name.trim())}>{f.addToQueue}</Button></>}>
        <div className="space-y-4">
          <Field label={f.client} group>
            {draft.clientId ? (
              <div className="flex items-center justify-between rounded-xl border border-line px-3 py-2 text-sm"><span className="font-bold">{clientName(draft.clientId)}</span><button type="button" className="text-xs text-primary" onClick={() => setDraft({ ...draft, clientId: "" })}>{t.u.common.edit}</button></div>
            ) : (
              <>
                <Input placeholder={t.u.journal.pickClient} value={q} onChange={(e) => setQ(e.target.value)} />
                {found.length > 0 && <ul className="mt-1 divide-y divide-line rounded-xl border border-line">{found.map((c) => <li key={c.id}><button type="button" className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-paper" onClick={() => setDraft({ ...draft, clientId: c.id })}><span className="font-bold">{c.name}</span><span className="text-ink-soft">{c.phone}</span></button></li>)}</ul>}
                <div className="mt-2 grid gap-2 sm:grid-cols-2"><Input placeholder={`${f.walkIn}: ${t.u.common.fullName}`} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /><Input placeholder={t.u.common.phone} value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} /></div>
              </>
            )}
          </Field>
          <Field label={f.nurse}>
            <Select value={draft.staffId} onChange={(e) => setDraft({ ...draft, staffId: e.target.value })}>
              <option value="">{f.anyNurse}</option>
              {nurses.map((n) => <option key={n.id} value={n.id}>{n.name}{busyIds.has(n.id) ? ` · ${f.busy}` : ""}</option>)}
            </Select>
          </Field>
          <Field label={t.u.journal.services} group>
            <div className="space-y-1.5">
              {db.services.filter((s) => s.active).map((s) => {
                const on = draft.serviceIds.includes(s.id);
                return <button key={s.id} type="button" onClick={() => setDraft({ ...draft, serviceIds: on ? draft.serviceIds.filter((x) => x !== s.id) : [...draft.serviceIds, s.id] })} className={`press flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm ${on ? "border-gold bg-gold-soft" : "border-line"}`}><span>{s.name}</span><span className="text-xs text-ink-soft">{s.duration} {f.min} · {fmtMoney(s.price)}</span></button>;
              })}
            </div>
          </Field>
          <span className="hidden"><Icon name="users" /></span>
        </div>
      </Drawer>
    </div>
  );
}
