"use client";

import { useState } from "react";
import { Badge, Button, Cell, Drawer, Field, Input, PageHeader, Row, Select, Table, Toggle } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Service } from "@/data/types";
import { PackagesSection } from "./packages";
import { useI18n } from "@/i18n/provider";
import { fmtMoney } from "@/lib/money";

export function ServicesScreen({ addons }: { addons: boolean }) {
  const { db, update, canManage } = useStore();
  const manage = canManage(addons ? "dop-uslugi" : "uslugi");
  const { t } = useI18n();
  const u = t.u;
  const [editing, setEditing] = useState<Service | null>(null);

  const list = db.services.filter((s) => s.addon === addons);
  const catName = (id: string) => db.categories.find((c) => c.id === id)?.name ?? "";

  function openNew() {
    setEditing({ id: newId("sv_"), name: "", categoryId: db.categories[0]?.id ?? "", duration: 30, price: 0, pricesByPosition: {}, addon: addons, materialsCost: 0, discountAtExpense: "salon", online: !addons, active: true });
  }
  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, services: d.services.some((s) => s.id === editing.id) ? d.services.map((s) => (s.id === editing.id ? editing : s)) : [...d.services, editing] }));
    setEditing(null);
  }
  const num = (v: string) => Math.max(0, Number(v) || 0);

  return (
    <div>
      <PageHeader title={addons ? u.services.addons : u.services.title} subtitle={addons ? u.services.addonsSubtitle : u.services.subtitle} actions={manage ? <Button variant="primary" onClick={openNew}>{u.common.add}</Button> : undefined} />
      <Table head={[u.common.name, u.services.category, u.services.duration, u.common.price, u.services.materials, u.services.discountAt, u.services.online]} empty={u.common.nothing}>
        {list.map((s) => {
          const prices = [s.price, ...Object.values(s.pricesByPosition)];
          const min = Math.min(...prices), max = Math.max(...prices);
          return (
            <Row key={s.id} onClick={() => setEditing(s)}>
              <Cell><span className="font-semibold">{s.name}</span>{!s.active && <Badge> {u.common.inactive}</Badge>}</Cell>
              <Cell className="text-ink-soft">{catName(s.categoryId)}</Cell>
              <Cell>{s.duration} {u.services.minutes}</Cell>
              <Cell right>{min === max ? fmtMoney(s.price) : `${fmtMoney(min)}–${fmtMoney(max)}`}</Cell>
              <Cell right>{fmtMoney(s.materialsCost)}</Cell>
              <Cell>{s.discountAtExpense === "salon" ? u.services.salon : <Badge tone="warn">{u.services.master}</Badge>}</Cell>
              <Cell>{s.online ? u.common.yes : u.common.no}</Cell>
            </Row>
          );
        })}
      </Table>

      <Drawer
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing && db.services.some((s) => s.id === editing.id) ? editing.name : u.services.newService}
        footer={<><Button onClick={() => setEditing(null)}>{u.common.cancel}</Button>{manage && <Button variant="primary" onClick={save} disabled={!editing?.name.trim()}>{u.common.save}</Button>}</>}
      >
        {editing && (
          <div className="space-y-4">
            <Field label={u.common.name}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={u.services.category}>
                <Select value={editing.categoryId} onChange={(e) => setEditing({ ...editing, categoryId: e.target.value })}>
                  {db.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
              <Field label={`${u.services.duration}, ${u.services.minutes}`}><Input type="number" min={5} step={5} value={editing.duration} onChange={(e) => setEditing({ ...editing, duration: num(e.target.value) })} /></Field>
              <Field label={u.services.basePrice}><Input type="number" min={0} value={editing.price} onChange={(e) => setEditing({ ...editing, price: num(e.target.value) })} /></Field>
              <Field label={u.services.materials} hint={u.services.materialsHint}><Input type="number" min={0} value={editing.materialsCost} onChange={(e) => setEditing({ ...editing, materialsCost: num(e.target.value) })} /></Field>
            </div>
            <Field label={u.services.priceBy} group>
              <div className="grid gap-2 sm:grid-cols-2">
                {db.positions.filter((p) => p.id !== "p_owner" && p.id !== "p_admin").map((p) => (
                  <label key={p.id} className="flex items-center gap-2 text-sm">
                    <span className="w-28 shrink-0 text-ink-soft">{p.name}</span>
                    <Input type="number" min={0} placeholder={String(editing.price)} value={editing.pricesByPosition[p.id] ?? ""} onChange={(e) => {
                      const next = { ...editing.pricesByPosition };
                      if (e.target.value === "") delete next[p.id]; else next[p.id] = num(e.target.value);
                      setEditing({ ...editing, pricesByPosition: next });
                    }} />
                  </label>
                ))}
              </div>
            </Field>
            <Field label={u.services.discountAt} hint={u.services.discountHint}>
              <Select value={editing.discountAtExpense} onChange={(e) => setEditing({ ...editing, discountAtExpense: e.target.value as Service["discountAtExpense"] })}>
                <option value="salon">{u.services.salon}</option>
                <option value="master">{u.services.master}</option>
              </Select>
            </Field>
            <Toggle label={u.services.online} checked={editing.online} onChange={(v) => setEditing({ ...editing, online: v })} />
            <Toggle label={u.services.isAddon} checked={editing.addon} onChange={(v) => setEditing({ ...editing, addon: v })} />
            <Toggle label={u.common.active} checked={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
          </div>
        )}
      </Drawer>
      {!addons && <PackagesSection />}
    </div>
  );
}
