"use client";

import { useState } from "react";
import { Badge, Button, Card, Cell, Drawer, Field, Input, PageHeader, Row, Segmented, Select, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Product } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { toIsoLocal } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

export function InventoryScreen() {
  const { db, update, branchId, userId, canManage } = useStore();
  const manage = canManage("sklad");
  const { t } = useI18n();
  const inv = t.u.inventory;
  const [tab, setTab] = useState<"stock" | "receipt" | "writeoff">("stock");
  const [editing, setEditing] = useState<Product | null>(null);
  const [op, setOp] = useState<{ productId: string; qty: number; cost: number; reason: string }>({ productId: db.products[0]?.id ?? "", qty: 1, cost: db.products[0]?.cost ?? 0, reason: "" });
  const branch = branchId === "all" ? db.branches[0].id : branchId;
  const list = db.products.filter((p) => p.branchId === branch);

  function saveProduct() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, products: d.products.some((p) => p.id === editing.id) ? d.products.map((p) => (p.id === editing.id ? editing : p)) : [...d.products, editing] }));
    setEditing(null);
  }
  function receipt() {
    if (!op.productId || op.qty <= 0) return;
    update((d) => {
      const reg = d.registers.find((r) => r.branchId === branch && r.kind === "cash")?.id ?? d.registers[0].id;
      const p = d.products.find((x) => x.id === op.productId)!;
      return {
        ...d,
        products: d.products.map((x) => (x.id === op.productId ? { ...x, stock: x.stock + op.qty, cost: op.cost || x.cost } : x)),
        cashOps: [...d.cashOps, { id: newId("co"), branchId: branch, registerId: reg, date: toIsoLocal(new Date()), kind: "out", article: "Материалы", amount: op.qty * (op.cost || p.cost), staffId: userId, comment: `${inv.receipt}: ${p.name} × ${op.qty}`, refType: "receipt", refId: null }],
        audit: [{ id: newId("a"), at: toIsoLocal(new Date()), staffId: userId, entity: "product", entityId: p.id, action: "update" as const, summary: `${inv.receipt}: ${p.name} +${op.qty}` }, ...d.audit],
      };
    });
    setTab("stock");
  }
  function writeOff() {
    if (!op.productId || op.qty <= 0) return;
    update((d) => {
      const p = d.products.find((x) => x.id === op.productId)!;
      return {
        ...d,
        products: d.products.map((x) => (x.id === op.productId ? { ...x, stock: Math.max(0, x.stock - op.qty) } : x)),
        audit: [{ id: newId("a"), at: toIsoLocal(new Date()), staffId: userId, entity: "product", entityId: p.id, action: "update" as const, summary: `${inv.writeOff}: ${p.name} −${op.qty}${op.reason ? ` (${op.reason})` : ""}` }, ...d.audit],
      };
    });
    setTab("stock");
  }

  return (
    <div>
      <PageHeader title={inv.title} subtitle={inv.subtitle} actions={manage ? <Button variant="primary" onClick={() => setEditing({ id: newId("pr"), name: "", category: "", stock: 0, minStock: 0, cost: 0, price: 0, branchId: branch })}>{inv.newProduct}</Button> : undefined} />
      <div className="mb-4"><Segmented value={tab} onChange={setTab} options={manage ? [{ value: "stock", label: inv.tabs.stock }, { value: "receipt", label: inv.tabs.receipt }, { value: "writeoff", label: inv.tabs.writeoff }] : [{ value: "stock", label: inv.tabs.stock }]} /></div>
      {tab === "stock" && (
        <Table head={[t.u.common.name, inv.category, inv.stock, inv.minStock, inv.cost, inv.price]} empty={t.u.common.nothing}>
          {list.map((p) => (
            <Row key={p.id} onClick={() => setEditing(p)}>
              <Cell className="font-semibold">{p.name}</Cell>
              <Cell className="text-ink-soft">{p.category}</Cell>
              <Cell right>{p.stock} {p.stock <= p.minStock && <Badge tone="bad">{inv.low}</Badge>}</Cell>
              <Cell right className="text-ink-soft">{p.minStock}</Cell>
              <Cell right>{fmtMoney(p.cost)}</Cell>
              <Cell right>{p.price > 0 ? fmtMoney(p.price) : <Badge>{inv.notForSale}</Badge>}</Cell>
            </Row>
          ))}
        </Table>
      )}
      {tab !== "stock" && (
        <Card className="max-w-xl p-4">
          <p className="mb-3 text-xs text-ink-soft">{tab === "receipt" ? inv.receiptHint : inv.writeoffHint}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.u.common.name}><Select value={op.productId} onChange={(e) => { const p = db.products.find((x) => x.id === e.target.value); setOp({ ...op, productId: e.target.value, cost: p?.cost ?? 0 }); }}>{list.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.stock}</option>)}</Select></Field>
            <Field label={inv.qty}><Input type="number" min={1} value={op.qty} onChange={(e) => setOp({ ...op, qty: Math.max(1, Number(e.target.value) || 1) })} /></Field>
            {tab === "receipt" ? <Field label={inv.cost}><Input type="number" min={0} value={op.cost} onChange={(e) => setOp({ ...op, cost: Number(e.target.value) || 0 })} /></Field> : <Field label={inv.reason}><Input value={op.reason} onChange={(e) => setOp({ ...op, reason: e.target.value })} /></Field>}
          </div>
          <Button variant="primary" className="mt-4" onClick={tab === "receipt" ? receipt : writeOff}>{tab === "receipt" ? inv.receipt : inv.writeOff}</Button>
        </Card>
      )}
      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing && db.products.some((p) => p.id === editing.id) ? editing.name : inv.newProduct} footer={<><Button onClick={() => setEditing(null)}>{t.u.common.cancel}</Button>{manage && <Button variant="primary" onClick={saveProduct} disabled={!editing?.name.trim()}>{t.u.common.save}</Button>}</>}>
        {editing && (
          <div className="space-y-4">
            <Field label={t.u.common.name}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <Field label={inv.category}><Input value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={inv.stock}><Input type="number" min={0} value={editing.stock} onChange={(e) => setEditing({ ...editing, stock: Number(e.target.value) || 0 })} /></Field>
              <Field label={inv.minStock}><Input type="number" min={0} value={editing.minStock} onChange={(e) => setEditing({ ...editing, minStock: Number(e.target.value) || 0 })} /></Field>
              <Field label={inv.cost}><Input type="number" min={0} value={editing.cost} onChange={(e) => setEditing({ ...editing, cost: Number(e.target.value) || 0 })} /></Field>
              <Field label={inv.price} hint={inv.notForSale + ": 0"}><Input type="number" min={0} value={editing.price} onChange={(e) => setEditing({ ...editing, price: Number(e.target.value) || 0 })} /></Field>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
