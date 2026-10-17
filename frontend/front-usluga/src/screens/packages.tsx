"use client";

import { useState } from "react";
import { Badge, Button, Card, ConfirmButton, Drawer, Empty, Field, Input, Toggle } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { ClientPackage, PackageTemplate } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, fmtDate, parseIso, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

// Шаблоны абонементов: настраиваются в разделе «Услуги», продаются в «Продаже».
export function PackagesSection() {
  const { db, update, canManage } = useStore();
  const manage = canManage("uslugi");
  const { t } = useI18n();
  const pk = t.u.packages;
  const [editing, setEditing] = useState<PackageTemplate | null>(null);
  const services = db.services.filter((s) => !s.addon && s.active);

  function save() {
    if (!editing || !editing.name.trim() || !editing.serviceIds.length || editing.visits < 1) return;
    update((d) => ({ ...d, packages: d.packages.some((x) => x.id === editing.id) ? d.packages.map((x) => (x.id === editing.id ? editing : x)) : [...d.packages, editing] }));
    setEditing(null);
  }
  const fullPrice = (p: PackageTemplate) => p.serviceIds.length ? Math.round((p.serviceIds.reduce((s, id) => s + (db.services.find((x) => x.id === id)?.price ?? 0), 0) / p.serviceIds.length) * p.visits) : 0;

  return (
    <section className="mt-8">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-tight">{pk.title}</h2>
          <p className="text-sm text-ink-soft">{pk.subtitle}</p>
        </div>
        {manage && <Button variant="primary" onClick={() => setEditing({ id: newId("pk"), name: "", serviceIds: services[0] ? [services[0].id] : [], visits: 5, validDays: 90, price: 0, active: true })}>{pk.newPackage}</Button>}
      </div>
      {db.packages.length === 0 ? <Empty text={pk.none} /> : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {db.packages.map((p) => (
            <Card key={p.id} className={`p-4 ${p.active ? "" : "opacity-60"}`}>
              <button type="button" className="w-full text-left" onClick={() => manage && setEditing(p)} disabled={!manage}>
                <div className="flex items-start justify-between gap-2">
                  <span className="font-bold">{p.name}</span>
                  {!p.active && <Badge>{t.u.common.inactive}</Badge>}
                </div>
                <div className="mt-1 text-xs text-ink-soft">{p.serviceIds.map((id) => db.services.find((s) => s.id === id)?.name).join(", ")}</div>
                <div className="mt-3 flex items-end justify-between">
                  <span className="text-2xl font-extrabold tabular-nums">{fmtMoney(p.price)}</span>
                  <span className="text-xs text-ink-soft">{p.visits} × {fmtMoney(Math.round(p.price / p.visits))} {pk.perVisit}</span>
                </div>
                <div className="mt-1 text-xs text-ink-soft">{pk.validFor.replace("{d}", String(p.validDays))}{fullPrice(p) > p.price && <b className="ml-2 text-positive">−{Math.round((1 - p.price / fullPrice(p)) * 100)} %</b>}</div>
              </button>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-2 text-xs text-ink-soft">{pk.hint}</p>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing && db.packages.some((x) => x.id === editing.id) ? editing.name : pk.newPackage}
        footer={<><Button onClick={() => setEditing(null)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={save} disabled={!editing?.name.trim() || !editing?.serviceIds.length}>{t.u.common.save}</Button></>}>
        {editing && (
          <div className="space-y-4">
            <Field label={t.u.common.name}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label={pk.visits}><Input type="number" min={1} value={editing.visits} onChange={(e) => setEditing({ ...editing, visits: Math.max(1, Number(e.target.value) || 1) })} /></Field>
              <Field label={pk.validDays}><Input type="number" min={1} value={editing.validDays} onChange={(e) => setEditing({ ...editing, validDays: Math.max(1, Number(e.target.value) || 1) })} /></Field>
              <Field label={pk.price} hint={fullPrice(editing) ? `${fmtMoney(fullPrice(editing))} ${t.u.common.total.toLowerCase()}` : undefined}><Input type="number" min={0} value={editing.price || ""} onChange={(e) => setEditing({ ...editing, price: Math.max(0, Number(e.target.value) || 0) })} /></Field>
            </div>
            <Field label={pk.services} group>
              <div className="space-y-1.5">
                {services.map((s) => {
                  const on = editing.serviceIds.includes(s.id);
                  return <button key={s.id} type="button" aria-pressed={on} onClick={() => setEditing({ ...editing, serviceIds: on ? editing.serviceIds.filter((x) => x !== s.id) : [...editing.serviceIds, s.id] })} className={`press flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm ${on ? "border-gold bg-gold-soft" : "border-line"}`}><span>{s.name}</span><span className="text-xs text-ink-soft">{fmtMoney(s.price)}</span></button>;
                })}
              </div>
            </Field>
            <Toggle label={t.u.common.active} checked={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
          </div>
        )}
      </Drawer>
    </section>
  );
}

function stateOf(p: ClientPackage, today: string): "active" | "frozen" | "expired" | "used" | "refunded" {
  if (p.status === "refunded") return "refunded";
  if (p.frozenFrom) return "frozen";
  if (p.visitsUsed >= p.visitsTotal) return "used";
  if (p.expiresAt < today) return "expired";
  return "active";
}

// Абонементы клиента в его карточке: остаток, срок, заморозка и возврат остатка.
export function ClientPackagesList({ clientId }: { clientId: string }) {
  const { db, update, branchId, userId, canManage } = useStore();
  const manage = canManage("klienty") && canManage("kassa");
  const { t, lang } = useI18n();
  const pk = t.u.packages;
  const today = todayKey();
  const items = db.clientPackages.filter((p) => p.clientId === clientId).sort((a, b) => b.purchasedAt.localeCompare(a.purchasedAt));
  const refundOf = (p: ClientPackage) => Math.round((p.price * (p.visitsTotal - p.visitsUsed)) / p.visitsTotal);
  const audit = (entityId: string, summary: string) => ({ id: newId("a"), at: toIsoLocal(new Date()), staffId: userId, entity: "package", entityId, action: "update" as const, summary });

  function freeze(p: ClientPackage) {
    update((d) => ({ ...d, clientPackages: d.clientPackages.map((x) => (x.id === p.id ? { ...x, frozenFrom: today } : x)), audit: [audit(p.id, `${pk.freeze}: ${p.name}`), ...d.audit] }));
  }
  // Разморозка: срок продлевается на число дней заморозки.
  function unfreeze(p: ClientPackage) {
    if (!p.frozenFrom) return;
    const days = Math.max(0, Math.round((parseIso(today).getTime() - parseIso(p.frozenFrom).getTime()) / 86400000));
    update((d) => ({ ...d, clientPackages: d.clientPackages.map((x) => (x.id === p.id ? { ...x, frozenFrom: null, expiresAt: addDays(x.expiresAt, days) } : x)), audit: [audit(p.id, `${pk.unfreeze}: ${p.name}, +${days}`), ...d.audit] }));
  }
  function refund(p: ClientPackage) {
    const amount = refundOf(p);
    const now = toIsoLocal(new Date());
    update((d) => {
      const branch = branchId === "all" ? d.branches[0].id : branchId;
      const reg = d.registers.find((r) => r.branchId === branch && r.kind === "cash")?.id ?? d.registers[0].id;
      return {
        ...d,
        clientPackages: d.clientPackages.map((x) => (x.id === p.id ? { ...x, status: "refunded" as const, refundAmount: amount, frozenFrom: null } : x)),
        cashOps: amount > 0 ? [...d.cashOps, { id: newId("co"), branchId: branch, registerId: reg, date: now, kind: "out" as const, article: "Возврат", amount, staffId: userId, comment: `${pk.refundRest}: ${p.name}, ${d.clients.find((c) => c.id === p.clientId)?.name ?? ""}`, refType: null, refId: null }] : d.cashOps,
        audit: [audit(p.id, `${pk.refundRest}: ${p.name}, ${fmtMoney(amount)}`), ...d.audit],
      };
    });
  }

  if (!items.length) return <Empty text={pk.noClientPackages} />;
  return (
    <div className="space-y-2">
      {items.map((p) => {
        const st = stateOf(p, today);
        const left = p.visitsTotal - p.visitsUsed;
        return (
          <div key={p.id} className="rounded-xl border border-line p-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <span className="font-bold">{p.name}</span>
              <Badge tone={st === "active" ? "good" : st === "frozen" ? "info" : st === "refunded" ? "bad" : "neutral"}>
                {st === "active" ? `${pk.left} ${left}` : st === "frozen" ? pk.frozen : st === "expired" ? pk.expired : st === "used" ? pk.used : pk.refunded}
              </Badge>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-gold" style={{ width: `${(p.visitsUsed / p.visitsTotal) * 100}%` }} /></div>
            <div className="mt-1.5 flex flex-wrap justify-between gap-2 text-xs text-ink-soft">
              <span>{p.visitsUsed} / {p.visitsTotal} · {fmtMoney(p.price)}</span>
              <span>{pk.expires} {fmtDate(p.expiresAt, lang, { day: "numeric", month: "short", year: "numeric" })}{p.refundAmount > 0 && ` · −${fmtMoney(p.refundAmount)}`}</span>
            </div>
            {manage && (st === "active" || st === "frozen") && (
              <div className="mt-2 flex flex-wrap gap-2">
                {st === "active" ? <Button size="sm" onClick={() => freeze(p)}>{pk.freeze}</Button> : <Button size="sm" variant="primary" onClick={() => unfreeze(p)}>{pk.unfreeze}</Button>}
                {left > 0 && <ConfirmButton onConfirm={() => refund(p)}>{`${pk.refundRest} ${fmtMoney(refundOf(p))}`}</ConfirmButton>}
              </div>
            )}
          </div>
        );
      })}
      <p className="text-xs text-ink-soft">{pk.refundHint}</p>
    </div>
  );
}
