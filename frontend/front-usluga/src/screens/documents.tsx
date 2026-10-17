"use client";

import { useState } from "react";
import { Badge, Button, Cell, Drawer, Field, Input, PageHeader, Row, Select, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { ClientDocument } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtDate, todayKey } from "@/lib/dates";

export function DocumentsScreen() {
  const { db, update, userId, canManage } = useStore();
  const manage = canManage("dokumenty-klientov");
  const { t, lang } = useI18n();
  const d = t.u.documents;
  const [editing, setEditing] = useState<ClientDocument | null>(null);
  const list = [...db.documents].sort((a, b) => b.date.localeCompare(a.date));

  function save() {
    if (!editing || !editing.title.trim() || !editing.clientId) return;
    update((x) => ({ ...x, documents: [...x.documents, editing] }));
    setEditing(null);
  }

  return (
    <div>
      <PageHeader title={d.title} subtitle={d.subtitle} actions={manage ? <Button variant="primary" onClick={() => setEditing({ id: newId("d"), clientId: db.clients[0]?.id ?? "", type: "consent", title: d.types.consent, date: todayKey(), addedById: userId })}>{t.u.common.add}</Button> : undefined} />
      <Table head={[t.u.common.date, d.client, d.type, t.u.common.name, d.addedBy]} empty={t.u.common.nothing}>
        {list.map((x) => (
          <Row key={x.id}>
            <Cell className="text-ink-soft">{fmtDate(x.date, lang, { day: "numeric", month: "short", year: "numeric" })}</Cell>
            <Cell className="font-semibold">{db.clients.find((c) => c.id === x.clientId)?.name}</Cell>
            <Cell><Badge tone={x.type === "consent" ? "good" : x.type === "photo" ? "info" : "neutral"}>{d.types[x.type]}</Badge></Cell>
            <Cell>{x.title}</Cell>
            <Cell className="text-ink-soft">{db.staff.find((s) => s.id === x.addedById)?.name ?? "—"}</Cell>
          </Row>
        ))}
      </Table>
      <Drawer open={!!editing} onClose={() => setEditing(null)} title={d.newDocument} footer={<><Button onClick={() => setEditing(null)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={save} disabled={!editing?.title.trim()}>{t.u.common.save}</Button></>}>
        {editing && (
          <div className="space-y-4">
            <Field label={d.client}><Select value={editing.clientId} onChange={(e) => setEditing({ ...editing, clientId: e.target.value })}>{db.clients.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.phone}</option>)}</Select></Field>
            <Field label={d.type}><Select value={editing.type} onChange={(e) => { const type = e.target.value as ClientDocument["type"]; setEditing({ ...editing, type, title: d.types[type] }); }}>{(["consent", "contract", "photo", "file"] as const).map((k) => <option key={k} value={k}>{d.types[k]}</option>)}</Select></Field>
            <Field label={d.titleField}><Input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} /></Field>
            <Field label={t.u.common.date}><Input type="date" value={editing.date} onChange={(e) => e.target.value && setEditing({ ...editing, date: e.target.value })} /></Field>
            <p className="text-xs text-ink-soft">{d.uploadHint}</p>
          </div>
        )}
      </Drawer>
    </div>
  );
}
