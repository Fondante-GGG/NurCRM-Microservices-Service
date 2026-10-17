"use client";

import { Badge, Button, Cell, PageHeader, Row, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { BookingRequest } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, todayKey } from "@/lib/dates";

export function RequestsScreen() {
  const { db, update, branchId, userId, canManage } = useStore();
  const manage = canManage("zayavki");
  const { t, lang } = useI18n();
  const r = t.u.requests;
  const list = db.requests.filter((x) => branchId === "all" || x.branchId === branchId).sort((a, b) => (a.status === "new" ? -1 : 1) - (b.status === "new" ? -1 : 1) || b.createdAt.localeCompare(a.createdAt));
  const fresh = list.filter((x) => x.status === "new").length;

  function convert(x: BookingRequest) {
    update((d) => {
      let client = d.clients.find((c) => c.phone.replace(/\D/g, "") === x.phone.replace(/\D/g, ""));
      let clients = d.clients;
      if (!client) {
        client = { id: newId("cl"), name: x.clientName, phone: x.phone, birthday: null, category: "new", notes: "", consent: true, createdAt: todayKey() };
        clients = [...clients, client];
      }
      const ids = (x.serviceIds?.length ? x.serviceIds : x.serviceId ? [x.serviceId] : [d.services[0].id]);
      const duration = ids.reduce((sum, id) => sum + (d.services.find((s) => s.id === id)?.duration ?? 0), 0);
      const staffId = x.staffId ?? d.staff.find((s) => s.role === "master" && s.branchIds.includes(x.branchId))?.id ?? "";
      const start = x.wishedAt ?? `${todayKey()}T18:00`;
      return {
        ...d,
        clients,
        appointments: [...d.appointments, { id: newId("ap"), branchId: x.branchId, staffId, clientId: client.id, start, duration, serviceIds: ids, status: "confirmed", source: x.source, createdById: userId, note: x.comment ?? "", visitId: null }],
        requests: d.requests.map((q) => (q.id === x.id ? { ...q, status: "converted" } : q)),
      };
    });
  }
  const tone = (s: BookingRequest["status"]) => (s === "new" ? "warn" : s === "converted" ? "good" : s === "declined" ? "bad" : "neutral");

  return (
    <div>
      <PageHeader title={fresh > 0 ? `${r.title} · ${fresh} ${r.newCount}` : r.title} subtitle={r.subtitle} />
      <Table head={[r.client, t.u.journal.services, t.u.journal.master, r.wished, r.source, t.u.common.status, ""]} empty={t.u.common.nothing}>
        {list.map((x) => (
          <Row key={x.id}>
            <Cell><span className="font-semibold">{x.clientName}</span><br /><span className="whitespace-nowrap text-xs text-ink-soft">{x.phone}</span></Cell>
            <Cell>{(x.serviceIds?.length ? x.serviceIds : x.serviceId ? [x.serviceId] : []).map((id) => db.services.find((s) => s.id === id)?.name).join(", ") || "—"}{x.comment && <span className="block text-xs text-ink-soft">{x.comment}</span>}</Cell>
            <Cell>{db.staff.find((s) => s.id === x.staffId)?.name ?? t.u.common.all}</Cell>
            <Cell className="whitespace-nowrap">{x.wishedAt ? `${fmtDate(x.wishedAt.slice(0, 10), lang, { day: "numeric", month: "short" })} ${x.wishedAt.slice(11)}` : <Badge tone="info">{r.anyTime}</Badge>}</Cell>
            <Cell className="whitespace-nowrap text-ink-soft">{t.u.sources[x.source]}</Cell>
            <Cell><Badge tone={tone(x.status)}>{r.statuses[x.status]}</Badge></Cell>
            <Cell right>
              {manage && x.status === "new" && (
                <span className="flex justify-end gap-2">
                  <Button size="sm" variant="primary" onClick={() => convert(x)}>{r.confirm}</Button>
                  <Button size="sm" onClick={() => update((d) => ({ ...d, requests: d.requests.map((q) => (q.id === x.id ? { ...q, status: "declined" } : q)) }))}>{r.decline}</Button>
                </span>
              )}
            </Cell>
          </Row>
        ))}
      </Table>
      <p className="mt-4 text-xs text-ink-soft"><b>{r.waitlist}.</b> {r.waitlistHint}</p>
    </div>
  );
}
