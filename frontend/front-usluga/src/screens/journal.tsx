"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, ConfirmButton, Drawer, Field, Input, Select, Toggle } from "@/components/ui";
import { Icon } from "@/components/icon";
import { newId, useStore } from "@/data/store";
import type { Appointment, AppointmentStatus, Client } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, fmtDate, hhmmOf, minutesOf, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { allowsFlow } from "@/lib/industry";

const ROW_H = 14; // px на 15 минут

export function JournalScreen() {
  const { db, update, branchId, userId, role, canManage } = useStore();
  const manage = canManage("zapisi");
  const { t, lang } = useI18n();
  const u = t.u;
  const router = useRouter();
  const [date, setDate] = useState(todayKey());
  const [editing, setEditing] = useState<Appointment | null>(null);

  const branch = branchId === "all" ? db.branches[0].id : branchId;
  const from = minutesOf(db.settings.workFrom);
  const to = minutesOf(db.settings.workTo);
  const rows = (to - from) / 15;

  const shiftsToday = db.shifts.filter((s) => s.date === date && s.branchId === branch);
  const busyIds = new Set(shiftsToday.filter((s) => s.fact === "missed").map((s) => s.staffId));
  function toggleBusy(staffId: string) {
    update((d) => {
      const sh = d.shifts.find((s) => s.staffId === staffId && s.date === date);
      const busy = sh?.fact === "missed";
      const shifts = sh ? d.shifts.map((s) => (s.id === sh.id ? { ...s, fact: busy ? "worked" as const : "missed" as const } : s)) : [...d.shifts, { id: newId("sh"), staffId, branchId: branch, date, from: "09:00", to: "21:00", breakMin: 0, fact: "missed" as const }];
      return { ...d, shifts };
    });
  }
  const masters = useMemo(() => {
    const all = db.staff.filter((s) => s.role === "master" && s.active && (role !== "master" || s.id === userId));
    const withShift = all.filter((s) => shiftsToday.some((sh) => sh.staffId === s.id && (sh.fact !== "missed" || allowsFlow(db.industry))));
    return withShift.length ? withShift : all.filter((s) => s.branchIds.includes(branch));
  }, [db.staff, shiftsToday, branch, role, userId]);

  const appts = db.appointments.filter((a) => a.start.startsWith(date) && a.branchId === branch && a.status !== "canceled");

  function startNew(staffId: string, minutes: number) {
    setEditing({
      id: newId("ap"), branchId: branch, staffId, clientId: "", start: `${date}T${hhmmOf(minutes)}`, duration: 0, serviceIds: [],
      status: "pending", source: "admin", createdById: userId, note: "", visitId: null,
    });
  }

  function load(staffId: string): number | null {
    const sh = shiftsToday.find((s) => s.staffId === staffId);
    if (!sh) return null;
    const shiftMin = minutesOf(sh.to) - minutesOf(sh.from) - sh.breakMin;
    const busy = appts.filter((a) => a.staffId === staffId && a.status !== "no_show").reduce((s, a) => s + a.duration, 0);
    return Math.min(100, Math.round((busy / shiftMin) * 100));
  }

  const statusTone = (s: AppointmentStatus) => (s === "paid" ? "good" : s === "arrived" ? "info" : s === "no_show" ? "bad" : s === "confirmed" ? "neutral" : "warn");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{u.journal.title}</h1>
          <p className="mt-1 text-sm text-ink-soft">{fmtDate(date, lang, { weekday: "long", day: "numeric", month: "long" })}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 md:flex-nowrap">
          <Button size="sm" onClick={() => setDate(addDays(date, -1))} aria-label={u.journal.prev}>‹</Button>
          <Button size="sm" onClick={() => setDate(todayKey())}>{u.common.today}</Button>
          <Button size="sm" onClick={() => setDate(addDays(date, 1))} aria-label={u.journal.next}>›</Button>
          <Input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} className="w-auto" aria-label={u.common.date} />
          {manage && <Button variant="primary" className="whitespace-nowrap" onClick={() => masters[0] && startNew(masters[0].id, Math.max(from, Math.ceil((new Date().getHours() * 60 + 15) / 15) * 15))}>{u.journal.newAppointment}</Button>}
        </div>
      </div>

      {masters.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line px-4 py-10 text-center text-sm text-ink-soft">{u.journal.noMasters}</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <div className="grid" style={{ gridTemplateColumns: `56px repeat(${masters.length}, minmax(160px, 1fr))` }}>
            <div className="sticky top-0 z-10 border-b border-line bg-card" />
            {masters.map((m) => {
              const l = load(m.id);
              return (
                <div key={m.id} className="sticky top-0 z-10 border-b border-l border-line bg-card px-3 py-2">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <span className="size-2.5 rounded-full" style={{ background: m.color }} />
                    <span className="truncate">{m.name.split(" ")[0]}</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-paper">
                    {l !== null && <div className={`h-1.5 rounded-full ${l > 80 ? "bg-danger" : l > 50 ? "bg-gold" : "bg-primary"}`} style={{ width: `${l}%` }} />}
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 text-xs text-ink-soft">
                    <span>{l === null ? u.journal.noShift : `${l} % ${u.journal.load}`}</span>
                    {allowsFlow(db.industry) && (manage || m.id === userId) && (
                      <button type="button" onClick={() => toggleBusy(m.id)} className={`press rounded-full px-2 py-0.5 text-[11px] font-bold ${busyIds.has(m.id) ? "bg-bad-soft text-[#b42318]" : "bg-positive-soft text-positive"}`}>{busyIds.has(m.id) ? u.flow.busy : u.flow.free}</button>
                    )}
                  </div>
                </div>
              );
            })}

            <div className="relative" style={{ height: rows * ROW_H }}>
              {Array.from({ length: rows / 4 + 1 }, (_, i) => (
                <div key={i} className={`absolute right-2 text-xs text-ink-soft ${i === 0 ? "" : "-translate-y-1/2"}`} style={{ top: i * 4 * ROW_H }}>
                  {hhmmOf(from + i * 60)}
                </div>
              ))}
            </div>
            {masters.map((m) => {
              const sh = shiftsToday.find((s) => s.staffId === m.id);
              const shFrom = sh ? minutesOf(sh.from) : from;
              const shTo = sh ? minutesOf(sh.to) : to;
              return (
                <div key={m.id} className="relative border-l border-line" style={{ height: rows * ROW_H }}>
                  {Array.from({ length: rows }, (_, i) => {
                    const minutes = from + i * 15;
                    const outside = minutes < shFrom || minutes >= shTo;
                    return (
                      <button
                        type="button"
                        key={i}
                        aria-label={`${m.name} ${hhmmOf(minutes)}`}
                        onClick={() => manage && startNew(m.id, minutes)}
                        className={`absolute inset-x-0 border-t ${i % 4 === 0 ? "border-line" : "border-line/40"} ${outside ? "bg-paper/80" : "hover:bg-primary/5"}`}
                        style={{ top: i * ROW_H, height: ROW_H }}
                      />
                    );
                  })}
                  {appts.filter((a) => a.staffId === m.id).map((a) => {
                    const startMin = minutesOf(a.start.slice(11));
                    const top = ((startMin - from) / 15) * ROW_H;
                    const h = (a.duration / 15) * ROW_H;
                    const client = db.clients.find((c) => c.id === a.clientId);
                    const names = a.serviceIds.map((id) => db.services.find((s) => s.id === id)?.name).join(", ");
                    const muted = a.status === "no_show";
                    return (
                      <button
                        type="button"
                        key={a.id}
                        onClick={() => setEditing(a)}
                        className={`press absolute inset-x-1 overflow-hidden rounded-md border-l-4 px-2 text-left shadow-sm hover:z-10 hover:shadow-md ${h < 2 * ROW_H ? "flex items-center py-0 text-[11px] leading-none" : "py-1 text-xs"} ${muted ? "bg-paper text-ink-soft line-through" : "text-ink"}`}
                        style={{ top: top + 1, height: Math.max(h - 2, ROW_H), borderLeftColor: m.color, background: muted ? undefined : a.status === "pending" ? "#fff" : `color-mix(in srgb, ${m.color} 10%, white)`, outline: a.status === "pending" ? `1px dashed ${m.color}` : undefined }}
                      >
                        <div className="truncate font-semibold">{client?.name ?? "—"}{h < 3 * ROW_H && <span className="font-normal text-ink-soft"> · {a.start.slice(11)}</span>}</div>
                        {h >= 3 * ROW_H && <div className="truncate text-ink-soft">{names}</div>}
                        {h >= 4 * ROW_H && <div className="mt-0.5"><Badge tone={statusTone(a.status)}>{u.statuses[a.status]}</Badge></div>}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <AppointmentDrawer appt={editing} onClose={() => setEditing(null)} onPay={(id) => router.push(`/usluga/prodazha?appointment=${id}`)} />
    </div>
  );
}

// Карточка записи: клиент, услуги, мастер, время, статусы.
export function AppointmentDrawer({ appt, onClose, onPay }: { appt: Appointment | null; onClose: () => void; onPay: (id: string) => void }) {
  const { db, update, userId } = useStore();
  const { t } = useI18n();
  const u = t.u;
  const [draft, setDraft] = useState<Appointment | null>(null);
  const [clientQuery, setClientQuery] = useState("");
  const [newClient, setNewClient] = useState<{ name: string; phone: string } | null>(null);
  const [key, setKey] = useState<string | null>(null);

  if (appt && key !== appt.id) {
    setKey(appt.id);
    setDraft(appt);
    setClientQuery("");
    setNewClient(null);
  }
  if (!appt || !draft) return null;
  return <AppointmentForm appt={appt} draft={draft} setDraft={setDraft} clientQuery={clientQuery} setClientQuery={setClientQuery} newClient={newClient} setNewClient={setNewClient} onClose={onClose} onPay={onPay} />;
}

type FormProps = {
  appt: Appointment;
  draft: Appointment;
  setDraft: (a: Appointment) => void;
  clientQuery: string;
  setClientQuery: (s: string) => void;
  newClient: { name: string; phone: string } | null;
  setNewClient: (c: { name: string; phone: string } | null) => void;
  onClose: () => void;
  onPay: (id: string) => void;
};

function AppointmentForm({ appt, draft, setDraft, clientQuery, setClientQuery, newClient, setNewClient, onClose, onPay }: FormProps) {
  const { db, update, userId, canManage } = useStore();
  const manage = canManage("zapisi");
  const { t } = useI18n();
  const u = t.u;

  const isNew = !db.appointments.some((a) => a.id === appt.id);
  const master = db.staff.find((s) => s.id === draft.staffId);
  const masterServices = db.services.filter((s) => s.active && (master?.serviceIds.includes(s.id) ?? true));
  const price = (id: string) => {
    const s = db.services.find((x) => x.id === id);
    if (!s) return 0;
    return s.pricesByPosition?.[master?.positionId ?? ""] ?? s.price ?? 0;
  };
  const duration = draft.serviceIds.reduce((sum, id) => sum + (db.services.find((s) => s.id === id)?.duration ?? 0), 0);
  const total = draft.serviceIds.reduce((sum, id) => sum + price(id), 0);
  const client = db.clients.find((c) => c.id === draft.clientId);
  const found = clientQuery.trim().length >= 2 ? db.clients.filter((c) => (c.name + c.phone).toLowerCase().includes(clientQuery.toLowerCase())).slice(0, 6) : [];
  const canSave = draft.serviceIds.length > 0 && (draft.clientId || (newClient && newClient.name.trim()));

  function persist(next: Appointment) {
    update((d) => {
      let clients = d.clients;
      let clientId = next.clientId;
      if (!clientId && newClient && newClient.name.trim()) {
        const c: Client = { id: newId("cl"), name: newClient.name.trim(), phone: newClient.phone.trim(), birthday: null, category: "new", notes: "", consent: true, createdAt: todayKey() };
        clients = [...clients, c];
        clientId = c.id;
      }
      const a = { ...next, clientId, duration };
      const exists = d.appointments.some((x) => x.id === a.id);
      return { ...d, clients, appointments: exists ? d.appointments.map((x) => (x.id === a.id ? a : x)) : [...d.appointments, a] };
    });
  }
  function save() {
    if (!canSave) return;
    persist(draft);
    onClose();
  }
  function setStatus(status: AppointmentStatus) {
    const next = { ...draft, status };
    setDraft(next);
    persist(next);
    if (status === "canceled") onClose();
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title={isNew ? u.journal.newAppointment : u.journal.appointment}
      footer={
        !manage ? null : draft.status === "paid" ? (
          <span className="mr-auto text-sm text-ink-soft">{u.journal.paidHint}</span>
        ) : (
          <>
            {!isNew && <ConfirmButton onConfirm={() => setStatus("canceled")}>{u.journal.cancelAppt}</ConfirmButton>}
            <span className="flex-1" />
            {!isNew && draft.status === "pending" && <Button size="sm" onClick={() => setStatus("confirmed")}>{u.journal.confirm}</Button>}
            {!isNew && (draft.status === "pending" || draft.status === "confirmed") && <Button size="sm" onClick={() => setStatus("arrived")}>{u.journal.arrived}</Button>}
            {!isNew && (draft.status === "pending" || draft.status === "confirmed") && <Button size="sm" onClick={() => setStatus("no_show")}>{u.journal.noShow}</Button>}
            {!isNew && draft.status !== "no_show" && <Button variant="primary" size="sm" onClick={() => { persist(draft); onPay(draft.id); }}>{u.journal.toPay}</Button>}
            {isNew ? <Button variant="primary" onClick={save} disabled={!canSave}>{u.common.save}</Button> : <Button onClick={save} disabled={!canSave}>{u.common.save}</Button>}
          </>
        )
      }
    >
      <div className="space-y-4">
        {!isNew && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
            <Badge tone={draft.status === "paid" ? "good" : draft.status === "no_show" ? "bad" : "neutral"}>{u.statuses[draft.status]}</Badge>
            <span>{u.journal.source}: {u.sources[draft.source]}</span>
            {draft.createdById && <span>· {u.journal.createdBy}: {db.staff.find((s) => s.id === draft.createdById)?.name}</span>}
          </div>
        )}

        <Field label={u.journal.client} group>
          {client ? (
            <div className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-sm">
              <span><span className="font-semibold">{client.name}</span> <span className="text-ink-soft">{client.phone}</span></span>
              {draft.status !== "paid" && <button type="button" className="text-xs text-primary" onClick={() => setDraft({ ...draft, clientId: "" })}>{u.common.edit}</button>}
            </div>
          ) : newClient ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder={u.common.fullName} value={newClient.name} onChange={(e) => setNewClient({ ...newClient, name: e.target.value })} />
              <Input placeholder={u.common.phone} value={newClient.phone} onChange={(e) => setNewClient({ ...newClient, phone: e.target.value })} />
            </div>
          ) : (
            <div>
              <Input placeholder={u.journal.pickClient} value={clientQuery} onChange={(e) => setClientQuery(e.target.value)} autoFocus={typeof window !== "undefined" && window.innerWidth >= 768} autoComplete="off" name="client" />
              {(found.length > 0 || clientQuery.trim().length >= 2) && (
                <ul className="mt-1 divide-y divide-line rounded-lg border border-line">
                  {found.map((c) => (
                    <li key={c.id}>
                      <button type="button" className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-paper" onClick={() => setDraft({ ...draft, clientId: c.id })}>
                        <span className="font-semibold">{c.name}</span><span className="text-ink-soft">{c.phone}</span>
                      </button>
                    </li>
                  ))}
                  <li>
                    <button type="button" className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-primary hover:bg-paper" onClick={() => setNewClient({ name: /\d/.test(clientQuery) ? "" : clientQuery, phone: /\d/.test(clientQuery) ? clientQuery : "" })}>
                      <Icon name="users" className="size-4" /> {u.journal.newClient}
                    </button>
                  </li>
                </ul>
              )}
            </div>
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label={u.journal.master}>
            <Select value={draft.staffId} onChange={(e) => setDraft({ ...draft, staffId: e.target.value })} disabled={draft.status === "paid"}>
              {db.staff.filter((s) => s.role === "master" && s.active).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
          <Field label={u.common.date}><Input type="date" value={draft.start.slice(0, 10)} disabled={draft.status === "paid"} onChange={(e) => e.target.value && setDraft({ ...draft, start: `${e.target.value}T${draft.start.slice(11)}` })} /></Field>
          <Field label={u.journal.time}><Input type="time" step={900} value={draft.start.slice(11)} disabled={draft.status === "paid"} onChange={(e) => e.target.value && setDraft({ ...draft, start: `${draft.start.slice(0, 10)}T${e.target.value}` })} /></Field>
        </div>

        <Field group label={u.journal.services} hint={draft.serviceIds.length ? `${duration} ${u.services.minutes} · ${fmtMoney(total)}` : u.journal.pickServices}>
          <div className="space-y-2 pt-1">
            {masterServices.map((s) => (
              <Toggle key={s.id} label={`${s.name} · ${s.duration} ${u.services.minutes} · ${fmtMoney(price(s.id))}`} checked={draft.serviceIds.includes(s.id)} onChange={(v) => draft.status !== "paid" && setDraft({ ...draft, serviceIds: v ? [...draft.serviceIds, s.id] : draft.serviceIds.filter((x) => x !== s.id) })} />
            ))}
          </div>
        </Field>

        <Field label={u.journal.note}><Input value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} /></Field>
        {isNew && <input type="hidden" value={userId} readOnly />}
      </div>
    </Drawer>
  );
}
