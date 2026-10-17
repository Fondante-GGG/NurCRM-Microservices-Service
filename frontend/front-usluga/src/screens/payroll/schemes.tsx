"use client";

import { useState } from "react";
import { AccrualExplain } from "@/components/accrual-explain";
import { Badge, Button, Card, Drawer, Field, Input, Select, Toggle } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Scheme, SchemeComponent } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtMoney } from "@/lib/money";
import { computeAccruals } from "@/lib/payroll/calc";

const KINDS: SchemeComponent["kind"][] = ["service_rate", "booking_fee", "monthly_salary", "daily_count_bonus", "branch_revenue_share", "shift_rate", "stepped_percent"];

function blank(kind: SchemeComponent["kind"]): SchemeComponent {
  switch (kind) {
    case "service_rate": return { kind, mode: "percent", value: 40, overrides: [], deductMaterials: true };
    case "booking_fee": return { kind, mode: "fixed", value: 20 };
    case "monthly_salary": return { kind, amount: 20000 };
    case "daily_count_bonus": return { kind, tiers: [{ minCount: 6, percent: 5 }] };
    case "branch_revenue_share": return { kind, percent: 10, threshold: 300000, metric: "revenue" };
    case "shift_rate": return { kind, mode: "per_shift", value: 500 };
    case "stepped_percent": return { kind, tiers: [{ minRevenue: 0, percent: 30 }, { minRevenue: 100000, percent: 35 }, { minRevenue: 150000, percent: 40 }] };
  }
}

export function SchemesTab() {
  const { db, update, canManage } = useStore();
  const manage = canManage("zarplata");
  const { t } = useI18n();
  const p = t.u.payroll;
  const [editing, setEditing] = useState<Scheme | null>(null);

  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, schemes: d.schemes.some((s) => s.id === editing.id) ? d.schemes.map((s) => (s.id === editing.id ? editing : s)) : [...d.schemes, editing] }));
    setEditing(null);
  }

  return (
    <div>
      {manage && <div className="mb-3 flex justify-end"><Button variant="primary" onClick={() => setEditing({ id: newId("s_"), name: "", positionId: null, effectiveFrom: new Date().toISOString().slice(0, 10), components: [blank("service_rate")] })}>{p.newScheme}</Button></div>}
      <div className="grid gap-4 md:grid-cols-2">
        {db.schemes.map((s) => {
          const people = db.staff.filter((x) => x.schemeId === s.id && x.active);
          return (
            <Card key={s.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold tracking-tight">{s.name}</h2>
                  <p className="mt-1 text-xs text-ink-soft">{p.position}: {db.positions.find((x) => x.id === s.positionId)?.name ?? p.anyPosition} · {p.effectiveFrom} {s.effectiveFrom}</p>
                </div>
                {manage && <Button size="sm" onClick={() => setEditing(s)}>{t.u.common.edit}</Button>}
              </div>
              <ul className="mt-3 space-y-1.5 text-sm">
                {s.components.map((c, i) => <li key={i} className="flex items-center gap-2"><Badge tone="info">{p.kinds[c.kind]}</Badge><span className="text-ink-soft">{summary(c, db.services)}</span></li>)}
              </ul>
              <p className="mt-3 text-xs text-ink-soft">{p.staffOnScheme}: {people.length ? people.map((x) => x.name.split(" ")[0]).join(", ") : p.nobody}</p>
            </Card>
          );
        })}
      </div>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing && db.schemes.some((s) => s.id === editing.id) ? editing.name : p.newScheme} wide
        footer={<><Button onClick={() => setEditing(null)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={save} disabled={!editing?.name.trim()}>{t.u.common.save}</Button></>}>
        {editing && <SchemeEditor scheme={editing} onChange={setEditing} />}
      </Drawer>
    </div>
  );
}

function summary(c: SchemeComponent, services: { id: string; name: string }[]): string {
  switch (c.kind) {
    case "service_rate": return `${c.mode === "percent" ? c.value + " %" : fmtMoney(c.value)}${c.overrides.length ? ` (+${c.overrides.length}: ${c.overrides.map((o) => services.find((s) => s.id === o.serviceId)?.name).join(", ")})` : ""}`;
    case "booking_fee": return c.mode === "percent" ? `${c.value}\u00a0%` : fmtMoney(c.value);
    case "monthly_salary": return fmtMoney(c.amount);
    case "daily_count_bonus": return c.tiers.map((x) => `${x.minCount}+ → ${x.percent}\u00a0%`).join(", ");
    case "branch_revenue_share": return `${c.percent} % от ${fmtMoney(c.threshold)}`;
    case "shift_rate": return `${fmtMoney(c.value)} ${c.mode === "per_hour" ? "/ ч" : "/ смена"}`;
    case "stepped_percent": return c.tiers.map((x) => `${fmtMoney(x.minRevenue)}+ → ${x.percent}\u00a0%`).join(", ");
  }
}

export function SchemeEditor({ scheme, onChange }: { scheme: Scheme; onChange: (s: Scheme) => void }) {
  const { db } = useStore();
  const { t } = useI18n();
  const p = t.u.payroll;
  const [exService, setExService] = useState(db.services[0]?.id ?? "");
  const [exDiscount, setExDiscount] = useState(0);
  const setComp = (i: number, c: SchemeComponent) => onChange({ ...scheme, components: scheme.components.map((x, j) => (j === i ? c : x)) });
  const num = (v: string) => Number(v) || 0;
  const missing = KINDS.filter((k) => !scheme.components.some((c) => c.kind === k));

  // Живой пример: один визит по этой схеме.
  const exSvc = db.services.find((s) => s.id === exService);
  const example = exSvc ? computeAccruals({
    period: "2026-01", schemes: [{ ...scheme, effectiveFrom: "2026-01-01" }], services: db.services, appointments: [], adjustments: [],
    staff: [{ id: "x", name: "", phone: "", positionId: scheme.positionId ?? "", branchIds: ["b"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2026-01-01", active: true, schemeId: scheme.id, serviceIds: [], color: "" }],
    visits: [{ id: "ex", appointmentId: null, branchId: "b", staffId: "x", clientId: null, closedAt: "2026-01-10T12:00", closedById: null, lines: [{ kind: exSvc.addon ? "addon" : "service", refId: exSvc.id, name: exSvc.name, price: exSvc.price, qty: 1, discount: exDiscount, discountAtExpense: exSvc.discountAtExpense, materialsCost: exSvc.materialsCost }], tip: 0, tipChannel: "direct", payment: { cash: exSvc.price - exDiscount, card: 0, balance: 0 }, total: exSvc.price - exDiscount, refundedAt: null, refundAmount: 0 }],
  }).filter((a) => a.source === "visit") : [];

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-3"><Field label={t.u.common.name}><Input value={scheme.name} onChange={(e) => onChange({ ...scheme, name: e.target.value })} /></Field></div>
        <Field label={p.position}>
          <Select value={scheme.positionId ?? ""} onChange={(e) => onChange({ ...scheme, positionId: e.target.value || null })}>
            <option value="">{p.anyPosition}</option>
            {db.positions.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </Select>
        </Field>
        <Field label={p.effectiveFrom}><Input type="date" value={scheme.effectiveFrom} onChange={(e) => e.target.value && onChange({ ...scheme, effectiveFrom: e.target.value })} /></Field>
        <p className="self-end pb-1 text-xs text-ink-soft">{p.noRetro}</p>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{p.components}</h3>
          {missing.length > 0 && (
            <Select value="" onChange={(e) => e.target.value && onChange({ ...scheme, components: [...scheme.components, blank(e.target.value as SchemeComponent["kind"])] })} className="w-auto">
              <option value="">{p.addComponent}</option>
              {missing.map((k) => <option key={k} value={k}>{p.kinds[k]}</option>)}
            </Select>
          )}
        </div>
        <div className="space-y-3">
          {scheme.components.map((c, i) => (
            <div key={i} className="anim-rise rounded-xl border border-line p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold">{p.kinds[c.kind]}</div>
                  <div className="text-xs text-ink-soft">{p.kindHints[c.kind]}</div>
                </div>
                <button type="button" aria-label={t.u.common.delete} className="press rounded-lg px-2 text-ink-soft hover:text-danger" onClick={() => onChange({ ...scheme, components: scheme.components.filter((_, j) => j !== i) })}>×</button>
              </div>
              <div className="mt-3">
                {c.kind === "service_rate" && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <Field label={p.mode}><Select value={c.mode} onChange={(e) => setComp(i, { ...c, mode: e.target.value as "percent" | "fixed" })}><option value="percent">{p.percent}</option><option value="fixed">{p.fixed}</option></Select></Field>
                      <Field label={p.value}><Input type="number" min={0} value={c.value} onChange={(e) => setComp(i, { ...c, value: num(e.target.value) })} /></Field>
                    </div>
                    <Toggle label={p.deductMaterials} checked={c.deductMaterials} onChange={(v) => setComp(i, { ...c, deductMaterials: v })} />
                    <Field label={p.overrides} group>
                      <div className="space-y-2">
                        {c.overrides.map((o, k) => (
                          <div key={k} className="grid grid-cols-[1fr_110px_90px_auto] gap-2">
                            <Select value={o.serviceId} onChange={(e) => setComp(i, { ...c, overrides: c.overrides.map((x, m) => (m === k ? { ...x, serviceId: e.target.value } : x)) })}>{db.services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
                            <Select value={o.mode} onChange={(e) => setComp(i, { ...c, overrides: c.overrides.map((x, m) => (m === k ? { ...x, mode: e.target.value as "percent" | "fixed" } : x)) })}><option value="percent">{p.percent}</option><option value="fixed">{p.fixed}</option></Select>
                            <Input type="number" min={0} value={o.value} onChange={(e) => setComp(i, { ...c, overrides: c.overrides.map((x, m) => (m === k ? { ...x, value: num(e.target.value) } : x)) })} />
                            <button type="button" aria-label={t.u.common.delete} className="press px-2 text-ink-soft hover:text-danger" onClick={() => setComp(i, { ...c, overrides: c.overrides.filter((_, m) => m !== k) })}>×</button>
                          </div>
                        ))}
                        <Button size="sm" onClick={() => setComp(i, { ...c, overrides: [...c.overrides, { serviceId: db.services[0]?.id ?? "", mode: "fixed", value: 250 }] })}>{p.addOverride}</Button>
                      </div>
                    </Field>
                  </div>
                )}
                {c.kind === "booking_fee" && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label={p.mode}><Select value={c.mode} onChange={(e) => setComp(i, { ...c, mode: e.target.value as "percent" | "fixed" })}><option value="fixed">{p.fixed}</option><option value="percent">{p.percent}</option></Select></Field>
                    <Field label={p.value}><Input type="number" min={0} value={c.value} onChange={(e) => setComp(i, { ...c, value: num(e.target.value) })} /></Field>
                  </div>
                )}
                {c.kind === "monthly_salary" && <Field label={p.amount}><Input type="number" min={0} value={c.amount} onChange={(e) => setComp(i, { ...c, amount: num(e.target.value) })} /></Field>}
                {c.kind === "daily_count_bonus" && (
                  <Field label={p.tiers} group>
                    <div className="space-y-2">
                      {c.tiers.map((tier, k) => (
                        <div key={k} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
                          <Field label={p.minCount}><Input type="number" min={1} value={tier.minCount} onChange={(e) => setComp(i, { ...c, tiers: c.tiers.map((x, m) => (m === k ? { ...x, minCount: num(e.target.value) } : x)) })} /></Field>
                          <Field label={p.bonusPercent}><Input type="number" min={0} value={tier.percent} onChange={(e) => setComp(i, { ...c, tiers: c.tiers.map((x, m) => (m === k ? { ...x, percent: num(e.target.value) } : x)) })} /></Field>
                          <button type="button" aria-label={t.u.common.delete} className="press px-2 pb-2 text-ink-soft hover:text-danger" onClick={() => setComp(i, { ...c, tiers: c.tiers.filter((_, m) => m !== k) })}>×</button>
                        </div>
                      ))}
                      <Button size="sm" onClick={() => setComp(i, { ...c, tiers: [...c.tiers, { minCount: (c.tiers.at(-1)?.minCount ?? 4) + 2, percent: (c.tiers.at(-1)?.percent ?? 0) + 5 }] })}>{p.addTier}</Button>
                    </div>
                  </Field>
                )}
                {c.kind === "branch_revenue_share" && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label={p.sharePercent}><Input type="number" min={0} value={c.percent} onChange={(e) => setComp(i, { ...c, percent: num(e.target.value) })} /></Field>
                    <Field label={p.threshold}><Input type="number" min={0} value={c.threshold} onChange={(e) => setComp(i, { ...c, threshold: num(e.target.value) })} /></Field>
                  </div>
                )}
                {c.kind === "shift_rate" && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label={p.shiftMode}><Select value={c.mode} onChange={(e) => setComp(i, { ...c, mode: e.target.value as "per_shift" | "per_hour" })}><option value="per_shift">{p.perShift}</option><option value="per_hour">{p.perHour}</option></Select></Field>
                    <Field label={p.value}><Input type="number" min={0} value={c.value} onChange={(e) => setComp(i, { ...c, value: num(e.target.value) })} /></Field>
                  </div>
                )}
                {c.kind === "stepped_percent" && (
                  <Field label={p.tiers} group>
                    <div className="space-y-2">
                      {c.tiers.map((tier, k) => (
                        <div key={k} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
                          <Field label={p.minRevenue}><Input type="number" min={0} value={tier.minRevenue} onChange={(e) => setComp(i, { ...c, tiers: c.tiers.map((x, m) => (m === k ? { ...x, minRevenue: num(e.target.value) } : x)) })} /></Field>
                          <Field label={p.steppedPercent}><Input type="number" min={0} value={tier.percent} onChange={(e) => setComp(i, { ...c, tiers: c.tiers.map((x, m) => (m === k ? { ...x, percent: num(e.target.value) } : x)) })} /></Field>
                          <button type="button" aria-label={t.u.common.delete} className="press px-2 pb-2 text-ink-soft hover:text-danger" onClick={() => setComp(i, { ...c, tiers: c.tiers.filter((_, m) => m !== k) })}>×</button>
                        </div>
                      ))}
                      <Button size="sm" onClick={() => setComp(i, { ...c, tiers: [...c.tiers, { minRevenue: (c.tiers.at(-1)?.minRevenue ?? 0) + 50000, percent: (c.tiers.at(-1)?.percent ?? 25) + 5 }] })}>{p.addTier}</Button>
                    </div>
                  </Field>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {scheme.components.some((c) => c.kind === "service_rate") && (
        <div className="rounded-xl bg-paper p-4">
          <h3 className="text-sm font-semibold">{p.example}</h3>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <Field label={p.exampleService}><Select value={exService} onChange={(e) => setExService(e.target.value)}>{db.services.map((s) => <option key={s.id} value={s.id}>{s.name} · {fmtMoney(s.price)}</option>)}</Select></Field>
            <Field label={p.exampleDiscount}><Input type="number" min={0} value={exDiscount} onChange={(e) => setExDiscount(num(e.target.value))} /></Field>
          </div>
          {example.map((a) => (
            <div key={a.id} className="mt-3">
              <div className="text-xl font-bold text-primary">{p.exampleResult}: {fmtMoney(a.amount)}</div>
              <AccrualExplain steps={a.steps} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
