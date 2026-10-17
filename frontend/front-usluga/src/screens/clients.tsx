"use client";

import { useMemo, useState } from "react";
import { Badge, Button, Cell, Drawer, Empty, Field, Input, PageHeader, Row, Segmented, Select, Table, Toggle } from "@/components/ui";
import { ClientPackagesList } from "./packages";
import { newId, useStore } from "@/data/store";
import type { Client, ClientCategory } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, fmtDate, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

export function ClientsScreen() {
  const { db, update, canManage } = useStore();
  const manage = canManage("klienty");
  const { t, lang } = useI18n();
  const u = t.u;
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | "lost" | "birthday">("all");
  const [editing, setEditing] = useState<Client | null>(null);
  const [tab, setTab] = useState<"profile" | "history" | "upcoming" | "packages">("profile");
  const today = todayKey();

  const stats = useMemo(() => {
    const m = new Map<string, { visits: number; last: string; spent: number }>();
    for (const v of db.visits) {
      if (!v.clientId) continue;
      const cur = m.get(v.clientId) ?? { visits: 0, last: "", spent: 0 };
      cur.visits += 1;
      cur.spent += v.total - v.refundAmount;
      if (v.closedAt > cur.last) cur.last = v.closedAt;
      m.set(v.clientId, cur);
    }
    return m;
  }, [db.visits]);

  const list = db.clients.filter((c) => {
    if (q && !(c.name + c.phone).toLowerCase().includes(q.toLowerCase())) return false;
    const st = stats.get(c.id);
    if (filter === "lost") return !st || st.last.slice(0, 10) < addDays(today, -30);
    if (filter === "birthday") return !!c.birthday && c.birthday.slice(5, 7) === today.slice(5, 7);
    return true;
  }).sort((a, b) => (stats.get(b.id)?.last ?? "").localeCompare(stats.get(a.id)?.last ?? ""));

  const catTone = (c: ClientCategory) => (c === "vip" ? "good" : c === "blacklist" ? "bad" : c === "new" ? "info" : "neutral");
  const dup = editing && editing.phone.trim() && db.clients.some((c) => c.id !== editing.id && c.phone.replace(/\D/g, "") === editing.phone.replace(/\D/g, ""));

  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, clients: d.clients.some((c) => c.id === editing.id) ? d.clients.map((c) => (c.id === editing.id ? editing : c)) : [...d.clients, editing] }));
    setEditing(null);
  }

  return (
    <div>
      <PageHeader title={u.clients.title} subtitle={u.clients.subtitle} actions={manage ? <Button variant="primary" onClick={() => { setTab("profile"); setEditing({ id: newId("cl"), name: "", phone: "", birthday: null, category: "new", notes: "", consent: true, createdAt: today }); }}>{u.common.add}</Button> : undefined} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input placeholder={u.common.search} value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Segmented value={filter} onChange={setFilter} options={[{ value: "all", label: u.clients.filterAll }, { value: "lost", label: u.clients.filterLost }, { value: "birthday", label: u.clients.filterBirthday }]} />
        <span className="text-sm text-ink-soft">{list.length}</span>
      </div>
      <Table head={[u.common.fullName, u.common.phone, u.clients.visits, u.clients.lastVisit, u.clients.spent, u.clients.category]} empty={u.common.nothing}>
        {list.map((c) => {
          const st = stats.get(c.id);
          return (
            <Row key={c.id} onClick={() => { setTab("profile"); setEditing(c); }}>
              <Cell className="font-semibold">{c.name}</Cell>
              <Cell className="text-ink-soft">{c.phone}</Cell>
              <Cell right>{st?.visits ?? 0}</Cell>
              <Cell>{st?.last ? fmtDate(st.last.slice(0, 10), lang, { day: "numeric", month: "short", year: "numeric" }) : "—"}</Cell>
              <Cell right>{fmtMoney(st?.spent ?? 0)}</Cell>
              <Cell><Badge tone={catTone(c.category)}>{u.clients.categories[c.category]}</Badge></Cell>
            </Row>
          );
        })}
      </Table>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing && db.clients.some((c) => c.id === editing.id) ? editing.name : u.clients.newClient}
        footer={<><Button onClick={() => setEditing(null)}>{u.common.cancel}</Button>{manage && <Button variant="primary" onClick={save} disabled={!editing?.name.trim()}>{u.common.save}</Button>}</>}>
        {editing && (
          <div className="space-y-4">
            <Segmented value={tab} onChange={setTab} options={[{ value: "profile", label: u.clients.tabProfile }, { value: "history", label: u.clients.tabHistory }, { value: "upcoming", label: u.clients.tabUpcoming }, { value: "packages", label: u.packages.title }]} />
            {tab === "profile" && (
              <>
                <Field label={u.common.fullName}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
                <Field label={u.common.phone} hint={dup ? u.clients.duplicate : undefined}><Input value={editing.phone} onChange={(e) => setEditing({ ...editing, phone: e.target.value })} /></Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label={u.clients.birthday}><Input type="date" value={editing.birthday ?? ""} onChange={(e) => setEditing({ ...editing, birthday: e.target.value || null })} /></Field>
                  <Field label={u.clients.category}>
                    <Select value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value as ClientCategory })}>
                      {(["new", "regular", "vip", "blacklist"] as const).map((c) => <option key={c} value={c}>{u.clients.categories[c]}</option>)}
                    </Select>
                  </Field>
                </div>
                <Field label={u.clients.notes}><Input value={editing.notes} onChange={(e) => setEditing({ ...editing, notes: e.target.value })} /></Field>
                <Toggle label={u.clients.consent} checked={editing.consent} onChange={(v) => setEditing({ ...editing, consent: v })} />
              </>
            )}
            {tab === "history" && (
              <HistoryList clientId={editing.id} />
            )}
            {tab === "packages" && <ClientPackagesList clientId={editing.id} />}
            {tab === "upcoming" && (
              <UpcomingList clientId={editing.id} />
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}

function HistoryList({ clientId }: { clientId: string }) {
  const { db } = useStore();
  const { t, lang } = useI18n();
  const items = db.visits.filter((v) => v.clientId === clientId).sort((a, b) => b.closedAt.localeCompare(a.closedAt));
  if (!items.length) return <Empty text={t.u.clients.noVisits} />;
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      {items.map((v) => (
        <li key={v.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
          <div>
            <div className="font-semibold">{v.lines.map((l) => l.name).join(", ")}</div>
            <div className="text-xs text-ink-soft">{fmtDate(v.closedAt.slice(0, 10), lang, { day: "numeric", month: "short", year: "numeric" })} · {db.staff.find((s) => s.id === v.staffId)?.name}</div>
          </div>
          <div className="text-right tabular-nums">
            <div className="font-semibold">{fmtMoney(v.total)}</div>
            {v.refundAmount > 0 && <Badge tone="bad">−{fmtMoney(v.refundAmount)}</Badge>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function UpcomingList({ clientId }: { clientId: string }) {
  const { db } = useStore();
  const { t, lang } = useI18n();
  const u = t.u;
  const items = db.appointments.filter((a) => a.clientId === clientId && a.start >= todayKey() && a.status !== "canceled" && a.status !== "paid").sort((a, b) => a.start.localeCompare(b.start));
  if (!items.length) return <Empty text={u.clients.noUpcoming} />;
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      {items.map((a) => (
        <li key={a.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
          <div>
            <div className="font-semibold">{a.serviceIds.map((id) => db.services.find((s) => s.id === id)?.name).join(", ")}</div>
            <div className="text-xs text-ink-soft">{fmtDate(a.start.slice(0, 10), lang, { weekday: "short", day: "numeric", month: "short" })} {a.start.slice(11)} · {db.staff.find((s) => s.id === a.staffId)?.name}</div>
          </div>
          <Badge>{u.statuses[a.status]}</Badge>
        </li>
      ))}
    </ul>
  );
}
