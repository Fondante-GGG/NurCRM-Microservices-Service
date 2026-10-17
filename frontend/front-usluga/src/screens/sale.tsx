"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccrualExplain } from "@/components/accrual-explain";
import { Badge, Button, Card, Cell, ConfirmButton, Field, Input, PageHeader, Row, Select, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import type { Appointment, ClientPackage, Visit, VisitLine } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, dateKeyOf, periodOf, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { computeAccruals, type AccrualWithSteps } from "@/lib/payroll/calc";

// К оплате по строке: списанная с абонемента услуга — 0.
const due = (l: VisitLine) => (l.packageId ? 0 : l.price * l.qty - l.discount);
const sumDue = (lines: VisitLine[]) => lines.reduce((s, l) => s + due(l), 0);

// Абонемент можно использовать: не возвращён, не заморожен, срок не истёк, посещения остались.
export function packageUsable(p: ClientPackage, today: string): boolean {
  return p.status === "active" && !p.frozenFrom && p.expiresAt >= today && p.visitsUsed < p.visitsTotal;
}

type Draft = {
  appointmentId: string | null;
  staffId: string;
  clientId: string | null;
  lines: VisitLine[];
  tip: number;
  tipChannel: "cash_register" | "direct";
  cash: number;
  card: number;
};

export function SaleScreen() {
  const { db, update, branchId, userId, canManage } = useStore();
  const manage = canManage("prodazha");
  const { t } = useI18n();
  const u = t.u;
  const router = useRouter();
  const params = useSearchParams();
  const apptId = params.get("appointment");
  const branch = branchId === "all" ? db.branches[0].id : branchId;

  const [draft, setDraft] = useState<Draft | null>(null);
  const [done, setDone] = useState<{ visit: Visit; accruals: AccrualWithSteps[] } | null>(null);
  const [splitOpen, setSplitOpen] = useState<number | null>(null);

  const masters = db.staff.filter((s) => s.role === "master" && s.active && s.branchIds.includes(branch));

  function lineFor(serviceId: string, staffId: string): VisitLine {
    const s = (db.services || []).find((x) => x.id === serviceId);
    if (!s) {
      return { kind: "service", refId: serviceId, name: "Услуга", price: 0, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 0 };
    }
    const pos = (db.staff || []).find((x) => x.id === staffId)?.positionId ?? "";
    const prices = s.pricesByPosition || {};
    return { kind: s.addon ? "addon" : "service", refId: s.id, name: s.name, price: prices[pos] ?? s.price ?? 0, qty: 1, discount: 0, discountAtExpense: s.discountAtExpense || "salon", materialsCost: s.materialsCost || 0 };
  }
  function fresh(appt: Appointment | null): Draft {
    const staffId = appt?.staffId ?? masters[0]?.id ?? "";
    const lines = appt ? appt.serviceIds.map((id) => lineFor(id, staffId)) : [];
    const total = sumDue(lines);
    return { appointmentId: appt?.id ?? null, staffId, clientId: appt?.clientId ?? null, lines, tip: 0, tipChannel: "direct", cash: total, card: 0 };
  }

  useEffect(() => {
    const appt = apptId ? db.appointments.find((a) => a.id === apptId) ?? null : null;
    setDone(null);
    setDraft(fresh(appt));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apptId]);

  const subtotal = draft?.lines.reduce((s, l) => s + l.price * l.qty, 0) ?? 0;
  const discountTotal = draft?.lines.reduce((s, l) => s + (l.packageId ? 0 : l.discount), 0) ?? 0;
  const packageTotal = draft?.lines.reduce((s, l) => s + (l.packageId ? l.price * l.qty : 0), 0) ?? 0;
  const total = subtotal - discountTotal - packageTotal;
  const pk = u.packages;
  const today = todayKey();
  // Абонементы клиента, доступные к списанию, с учётом строк, уже отмеченных в этом чеке.
  const clientPkgs = draft?.clientId ? db.clientPackages.filter((p) => p.clientId === draft.clientId && packageUsable(p, today)) : [];
  const leftOf = (p: ClientPackage) => p.visitsTotal - p.visitsUsed - (draft?.lines.filter((l) => l.packageId === p.id).reduce((s, l) => s + l.qty, 0) ?? 0);
  const pkgFor = (l: VisitLine) => clientPkgs.find((p) => p.serviceIds.includes(l.refId) && (l.packageId === p.id || leftOf(p) >= l.qty));
  const paid = (draft?.cash ?? 0) + (draft?.card ?? 0);
  const mismatch = Math.round(paid) !== Math.round(total);
  const appt = draft?.appointmentId ? db.appointments.find((a) => a.id === draft.appointmentId) : null;
  const warnings: string[] = [];
  if (appt && draft && appt.staffId !== draft.staffId) warnings.push(u.sale.warnExecutor);
  if (draft?.lines.some((l) => l.kind !== "product" && l.kind !== "package" && l.materialsCost === 0)) warnings.push(u.sale.warnMaterials);

  const todaySales = useMemo(() => db.visits.filter((v) => v.branchId === branch && dateKeyOf(v.closedAt) === todayKey()).sort((a, b) => b.closedAt.localeCompare(a.closedAt)), [db.visits, branch]);

  function setLine(i: number, patch: Partial<VisitLine>) {
    if (!draft) return;
    const lines = draft.lines.map((l, j) => (j === i ? { ...l, ...patch } : l));
    const t = sumDue(lines);
    setDraft({ ...draft, lines, cash: draft.card === 0 ? t : Math.max(0, t - draft.card) });
  }
  function addService(id: string) {
    if (!draft || !id) return;
    const lines = [...draft.lines, lineFor(id, draft.staffId)];
    const t = sumDue(lines);
    setDraft({ ...draft, lines, cash: draft.card === 0 ? t : Math.max(0, t - draft.card) });
  }
  function addPackage(id: string) {
    if (!draft || !id || !draft.clientId) return;
    const tpl = db.packages.find((x) => x.id === id)!;
    const lines = [...draft.lines, { kind: "package" as const, refId: tpl.id, name: `${pk.one}: ${tpl.name}`, price: tpl.price, qty: 1, discount: 0, discountAtExpense: "salon" as const, materialsCost: 0 }];
    const t = sumDue(lines);
    setDraft({ ...draft, lines, cash: draft.card === 0 ? t : Math.max(0, t - draft.card) });
  }
  // Списать строку с абонемента или вернуть обычную цену.
  function togglePackage(i: number) {
    if (!draft) return;
    const l = draft.lines[i];
    if (l.packageId) {
      const base = lineFor(l.refId, draft.staffId);
      setLine(i, { packageId: undefined, price: base.price, discount: 0 });
    } else {
      const p = pkgFor(l);
      if (p) setLine(i, { packageId: p.id, price: Math.round(p.price / p.visitsTotal), discount: 0 });
    }
  }
  function setSplit(i: number, other: string | null, share: number) {
    if (!draft) return;
    setLine(i, { splits: other ? [{ staffId: draft.staffId, share: 100 - share }, { staffId: other, share }] : undefined });
  }
  function addProduct(id: string) {
    if (!draft || !id) return;
    const p = db.products.find((x) => x.id === id)!;
    const lines = [...draft.lines, { kind: "product" as const, refId: p.id, name: p.name, price: p.price, qty: 1, discount: 0, discountAtExpense: "salon" as const, materialsCost: p.cost }];
    const t = sumDue(lines);
    setDraft({ ...draft, lines, cash: draft.card === 0 ? t : Math.max(0, t - draft.card) });
  }

  function closeVisit() {
    if (!draft || draft.lines.length === 0 || mismatch) return;
    const now = toIsoLocal(new Date());
    const visit: Visit = {
      id: newId("v"), appointmentId: draft.appointmentId, branchId: branch, staffId: draft.staffId, clientId: draft.clientId, closedAt: now, closedById: userId,
      lines: draft.lines, tip: draft.tip, tipChannel: draft.tipChannel, payment: { cash: draft.cash, card: draft.card, balance: 0 }, total, refundedAt: null, refundAmount: 0,
    };
    update((d) => {
      // Абонементы: продажа создаёт абонемент клиента, списание увеличивает использованные посещения.
      const bought: ClientPackage[] = visit.clientId ? visit.lines.filter((l) => l.kind === "package").flatMap((l) => {
        const tpl = d.packages.find((x) => x.id === l.refId);
        return tpl ? Array.from({ length: l.qty }, () => ({ id: newId("cp"), clientId: visit.clientId!, templateId: tpl.id, name: tpl.name, serviceIds: tpl.serviceIds, visitsTotal: tpl.visits, visitsUsed: 0, price: l.price - l.discount / l.qty, purchasedAt: todayKey(), expiresAt: addDays(todayKey(), tpl.validDays), frozenFrom: null, status: "active" as const, refundAmount: 0, visitId: visit.id })) : [];
      }) : [];
      const usedBy = (id: string) => visit.lines.filter((l) => l.packageId === id).reduce((s, l) => s + l.qty, 0);
      const clientPackages = [...d.clientPackages.map((p) => (usedBy(p.id) ? { ...p, visitsUsed: p.visitsUsed + usedBy(p.id) } : p)), ...bought];
      const regCash = d.registers.find((r) => r.branchId === branch && r.kind === "cash")?.id ?? d.registers[0].id;
      const regCard = d.registers.find((r) => r.branchId === branch && r.kind === "card")?.id ?? regCash;
      const ops = [...d.cashOps];
      if (visit.payment.cash > 0) ops.push({ id: newId("co"), branchId: branch, registerId: regCash, date: now, kind: "in", article: "Услуги", amount: visit.payment.cash, staffId: visit.staffId, comment: "", refType: "visit", refId: visit.id });
      if (visit.payment.card > 0) ops.push({ id: newId("co"), branchId: branch, registerId: regCard, date: now, kind: "in", article: "Услуги", amount: visit.payment.card, staffId: visit.staffId, comment: "", refType: "visit", refId: visit.id });
      if (visit.tip > 0 && visit.tipChannel === "cash_register") ops.push({ id: newId("co"), branchId: branch, registerId: regCash, date: now, kind: "in", article: "Чаевые", amount: visit.tip, staffId: visit.staffId, comment: "", refType: "visit", refId: visit.id });
      const products = d.products.map((p) => {
        const sold = visit.lines.filter((l) => l.kind === "product" && l.refId === p.id).reduce((s, l) => s + l.qty, 0);
        return sold ? { ...p, stock: Math.max(0, p.stock - sold) } : p;
      });
      return {
        ...d,
        visits: [...d.visits, visit],
        appointments: d.appointments.map((a) => (a.id === visit.appointmentId ? { ...a, status: "paid" as const, visitId: visit.id, staffId: visit.staffId } : a)),
        cashOps: ops,
        products,
        clientPackages,
        audit: [{ id: newId("a"), at: now, staffId: userId, entity: "visit", entityId: visit.id, action: "create" as const, summary: `Чек ${fmtMoney(total)}: ${visit.lines.map((l) => l.name).join(", ")}` }, ...d.audit],
      };
    });
    const accruals = computeAccruals({ period: periodOf(dateKeyOf(now)), staff: db.staff, schemes: db.schemes, services: db.services, visits: [visit], appointments: db.appointments, adjustments: [] }).filter((a) => a.source === "visit" || a.source === "booking");
    setDone({ visit, accruals });
  }

  function refund(v: Visit) {
    const now = toIsoLocal(new Date());
    update((d) => {
      const regCash = d.registers.find((r) => r.branchId === v.branchId && r.kind === "cash")?.id ?? d.registers[0].id;
      return {
        ...d,
        visits: d.visits.map((x) => (x.id === v.id ? { ...x, refundedAt: now, refundAmount: x.total } : x)),
        // Возврат чека: списанные посещения возвращаются на абонемент, купленный в этом чеке абонемент закрывается.
        clientPackages: d.clientPackages.map((p) => {
          const back = v.lines.filter((l) => l.packageId === p.id).reduce((s, l) => s + l.qty, 0);
          if (p.visitId === v.id) return { ...p, status: "refunded" as const, refundAmount: p.price };
          return back ? { ...p, visitsUsed: Math.max(0, p.visitsUsed - back) } : p;
        }),
        cashOps: [...d.cashOps, { id: newId("co"), branchId: v.branchId, registerId: regCash, date: now, kind: "out" as const, article: "Возврат", amount: v.total, staffId: userId, comment: "", refType: "visit" as const, refId: v.id }],
        audit: [{ id: newId("a"), at: now, staffId: userId, entity: "visit", entityId: v.id, action: "update" as const, summary: `Возврат чека ${fmtMoney(v.total)}` }, ...d.audit],
      };
    });
  }

  if (!draft) return null;

  if (done) {
    const masterAcc = done.accruals.filter((a) => a.staffId === done.visit.staffId);
    const masterTotal = masterAcc.reduce((s, a) => s + a.amount, 0);
    return (
      <div className="anim-pop max-w-2xl">
        <PageHeader title={u.sale.closed} subtitle={`${fmtMoney(done.visit.total)} · ${db.staff.find((s) => s.id === done.visit.staffId)?.name}`} />
        <Card className="p-5">
          <div className="text-sm font-semibold text-ink-soft">{u.explain.accrued}</div>
          <div className="mt-1 text-3xl font-bold tracking-tight text-primary">{fmtMoney(masterTotal)}</div>
          <div className="mt-4 text-sm font-semibold">{u.explain.howCounted}</div>
          <ul className="mt-2 space-y-2">
            {masterAcc.map((a) => (
              <li key={a.id} className="rounded-lg bg-paper px-3 py-2">
                <AccrualExplain steps={a.steps} />
              </li>
            ))}
          </ul>
          {done.accruals.filter((a) => a.staffId !== done.visit.staffId).map((a) => (
            <p key={a.id} className="mt-3 text-xs text-ink-soft">{db.staff.find((s) => s.id === a.staffId)?.name}: +{fmtMoney(a.amount)} ({u.explain.howCounted.toLowerCase()}: <AccrualExplain steps={a.steps} />)</p>
          ))}
        </Card>
        <div className="mt-4 flex gap-2">
          <Button variant="primary" onClick={() => router.push("/usluga/zapisi")}>{u.sale.backToJournal}</Button>
          <Button onClick={() => { setDone(null); setDraft(fresh(null)); router.replace("/usluga/prodazha"); }}>{u.sale.nextSale}</Button>
        </div>
      </div>
    );
  }

  const client = draft.clientId ? db.clients.find((c) => c.id === draft.clientId) : null;
  const services = db.services.filter((s) => s.active);

  return (
    <div>
      <PageHeader title={u.sale.title} subtitle={appt ? `${u.sale.fromAppointment}: ${appt.start.slice(11)}` : u.sale.subtitle} />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={u.sale.master}>
                <Select value={draft.staffId} onChange={(e) => setDraft({ ...draft, staffId: e.target.value, lines: draft.lines.map((l) => (l.kind === "product" || l.kind === "package" || l.packageId ? { ...l, splits: undefined } : lineFor(l.refId, e.target.value))) })}>
                  {masters.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </Select>
              </Field>
              <Field label={u.sale.client}>
                <Select value={draft.clientId ?? ""} onChange={(e) => {
                  // Другой клиент: списания с чужого абонемента снимаются, продажа абонемента без клиента невозможна.
                  const clientId = e.target.value || null;
                  const lines = draft.lines.filter((l) => clientId || l.kind !== "package").map((l) => (l.packageId ? { ...l, packageId: undefined, price: lineFor(l.refId, draft.staffId).price } : l));
                  const t = sumDue(lines);
                  setDraft({ ...draft, clientId, lines, cash: t, card: 0 });
                }}>
                  <option value="">{u.sale.noClient}</option>
                  {(client ? [client, ...db.clients.filter((c) => c.id !== client.id)] : db.clients).slice(0, 80).map((c) => <option key={c.id} value={c.id}>{c.name} · {c.phone}</option>)}
                </Select>
              </Field>
            </div>
          </Card>

          <Card className="p-4">
            <div className="mb-3">
              <div className="mb-2 text-sm font-semibold">{u.sale.lines}</div>
              <div className="grid gap-2 sm:grid-cols-3">
                <Select value="" onChange={(e) => addService(e.target.value)}>
                  <option value="">{u.sale.addService}</option>
                  {services.map((s) => <option key={s.id} value={s.id}>{s.name} · {fmtMoney(s.price)}</option>)}
                </Select>
                {db.packages.some((x) => x.active) && (draft.clientId ? (
                  <Select value="" onChange={(e) => addPackage(e.target.value)}>
                    <option value="">{pk.sell}</option>
                    {db.packages.filter((x) => x.active).map((x) => <option key={x.id} value={x.id}>{x.name} · {fmtMoney(x.price)}</option>)}
                  </Select>
                ) : (
                  <div className="flex h-11 items-center rounded-xl border border-dashed border-line-strong px-3.5 text-xs text-ink-soft" title={pk.needClient}>{pk.needClientShort}</div>
                ))}
                <Select value="" onChange={(e) => addProduct(e.target.value)}>
                  <option value="">{u.sale.addProduct}</option>
                  {db.products.filter((p) => p.price > 0).map((p) => <option key={p.id} value={p.id}>{p.name} · {fmtMoney(p.price)}</option>)}
                </Select>
              </div>
            </div>
            <div className="-mx-1 overflow-x-auto px-1">
            <table className="w-full min-w-[640px] text-sm">
              <thead><tr className="text-left text-xs text-ink-soft"><th className="py-1 font-semibold">{u.common.name}</th><th className="py-1 font-semibold">{u.common.price}</th><th className="py-1 font-semibold">{u.sale.qty}</th><th className="py-1 font-semibold">{u.sale.discount}</th><th className="py-1 font-semibold">{u.sale.discountAt}</th><th /><th /></tr></thead>
              <tbody>
                {draft.lines.map((l, i) => {
                  const pkg = l.kind === "service" || l.kind === "addon" ? pkgFor(l) : undefined;
                  const other = l.splits?.[1];
                  return (
                  <Fragment key={i}>
                  <tr className="border-t border-line">
                    <td className="min-w-44 py-2 pr-2 font-semibold">
                      {l.name}{l.kind === "addon" && <Badge>+</Badge>}
                      <div className="mt-1 flex flex-wrap gap-1.5 font-normal">
                        {(pkg || l.packageId) && (
                          <button type="button" onClick={() => togglePackage(i)} aria-pressed={!!l.packageId} className={`press rounded-full px-2 py-0.5 text-[11px] font-bold ${l.packageId ? "bg-gold text-primary" : "bg-gold-soft text-ink"}`}>
                            {pk.byPackage}{pkg && ` · ${pk.left} ${leftOf(pkg)}`}
                          </button>
                        )}
                        {(l.kind === "service" || l.kind === "addon") && masters.length > 1 && (
                          <button type="button" onClick={() => setSplitOpen(splitOpen === i ? null : i)} aria-expanded={splitOpen === i} className={`press rounded-full px-2 py-0.5 text-[11px] font-bold ${other ? "bg-primary text-white" : "bg-segment text-[#475467]"}`}>
                            {other ? `${u.split.action}: ${db.staff.find((x) => x.id === other.staffId)?.name.split(" ")[0]} ${other.share}\u00a0%` : u.split.action}
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="py-2 pr-2"><Input type="number" min={0} value={l.price} disabled={!!l.packageId} aria-label={u.common.price} onChange={(e) => setLine(i, { price: Number(e.target.value) || 0 })} className="h-9 w-24 px-2" /></td>
                    <td className="py-2 pr-2"><Input type="number" min={1} value={l.qty} aria-label={u.sale.qty} onChange={(e) => setLine(i, { qty: Math.max(1, Number(e.target.value) || 1) })} className="h-9 w-16 px-2" /></td>
                    <td className="py-2 pr-2"><Input type="number" min={0} value={l.discount} disabled={!!l.packageId || l.kind === "package"} aria-label={u.sale.discount} onChange={(e) => setLine(i, { discount: Math.min(l.price * l.qty, Number(e.target.value) || 0) })} className="h-9 w-24 px-2" /></td>
                    <td className="py-2 pr-2">
                      {l.kind !== "product" && l.kind !== "package" && (
                        <Select value={l.discountAtExpense} disabled={!!l.packageId} aria-label={u.sale.discountAt} onChange={(e) => setLine(i, { discountAtExpense: e.target.value as VisitLine["discountAtExpense"] })} className="h-9 w-28 px-2">
                          <option value="salon">{u.services.salon}</option>
                          <option value="master">{u.services.master}</option>
                        </Select>
                      )}
                    </td>
                    <td className="whitespace-nowrap py-2 text-right tabular-nums font-semibold">{l.packageId ? <span className="text-ink-soft line-through">{fmtMoney(l.price * l.qty)}</span> : fmtMoney(l.price * l.qty - l.discount)}</td>
                    <td className="py-2 pl-2"><button type="button" aria-label={u.common.delete} className="text-ink-soft hover:text-danger" onClick={() => { const lines = draft.lines.filter((_, j) => j !== i); const t = sumDue(lines); setDraft({ ...draft, lines, cash: t, card: 0 }); setSplitOpen(null); }}>×</button></td>
                  </tr>
                  {splitOpen === i && (
                    <tr className="anim-fade-in">
                      <td colSpan={7} className="pb-3">
                        <div className="flex flex-wrap items-end gap-3 rounded-xl bg-paper px-3 py-2">
                          <Field label={u.split.with}>
                            <Select value={other?.staffId ?? ""} onChange={(e) => setSplit(i, e.target.value || null, other?.share ?? 50)} className="w-auto">
                              <option value="">{u.split.remove}</option>
                              {masters.filter((m) => m.id !== draft.staffId).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                            </Select>
                          </Field>
                          {other && <Field label={u.split.share}><Input type="number" min={1} max={99} value={other.share} onChange={(e) => setSplit(i, other.staffId, Math.min(99, Math.max(1, Number(e.target.value) || 50)))} className="w-24" /></Field>}
                          <p className="pb-2 text-xs text-ink-soft">{u.split.hint}</p>
                        </div>
                      </td>
                    </tr>
                  )}
                  </Fragment>
                  );
                })}
              </tbody>
            </table>
            </div>
            {draft.lines.length === 0 && <p className="rounded-lg border border-dashed border-line px-3 py-4 text-center text-xs text-ink-soft">{u.common.addLinesHint}</p>}
            {warnings.length > 0 && (
              <ul className="mt-3 space-y-1">
                {warnings.map((w) => <li key={w} className="rounded-lg bg-gold/15 px-3 py-1.5 text-xs text-amber-900">{w}</li>)}
              </ul>
            )}
          </Card>
        </div>

        <Card className="h-fit p-4">
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between"><dt className="text-ink-soft">{u.sale.subtotal}</dt><dd className="tabular-nums">{fmtMoney(subtotal)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">{u.sale.discountTotal}</dt><dd className="tabular-nums">{fmtMoney(-discountTotal)}</dd></div>
            {packageTotal > 0 && <div className="flex justify-between"><dt className="text-ink-soft">{pk.byPackage}</dt><dd className="tabular-nums">{fmtMoney(-packageTotal)}</dd></div>}
            <div className="flex justify-between border-t border-line pt-2 text-lg font-bold"><dt>{u.sale.toPay}</dt><dd className="tabular-nums">{fmtMoney(total)}</dd></div>
          </dl>
          <div className="mt-4 space-y-3">
            <div className="text-sm font-semibold">{u.sale.payment}</div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => setDraft({ ...draft, cash: total, card: 0 })}>{u.sale.allCash}</Button>
              <Button size="sm" onClick={() => setDraft({ ...draft, cash: 0, card: total })}>{u.sale.allCard}</Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Field label={u.sale.cash}><Input type="number" min={0} value={draft.cash} onChange={(e) => setDraft({ ...draft, cash: Number(e.target.value) || 0 })} /></Field>
              <Field label={u.sale.card}><Input type="number" min={0} value={draft.card} onChange={(e) => setDraft({ ...draft, card: Number(e.target.value) || 0 })} /></Field>
            </div>
            {mismatch && <p className="text-xs text-danger">{u.sale.paymentMismatch}</p>}
            <div className="grid gap-2">
              <Field label={u.sale.tip}><Input type="number" min={0} value={draft.tip} onChange={(e) => setDraft({ ...draft, tip: Number(e.target.value) || 0 })} /></Field>
              <Field label={u.sale.tipChannel}>
                <Select value={draft.tipChannel} onChange={(e) => setDraft({ ...draft, tipChannel: e.target.value as Draft["tipChannel"] })}>
                  <option value="direct">{u.sale.tipDirect}</option>
                  <option value="cash_register">{u.sale.tipRegister}</option>
                </Select>
              </Field>
            </div>
          </div>
          <Button variant="primary" className="mt-4 w-full" onClick={closeVisit} disabled={!manage || draft.lines.length === 0 || mismatch}>{u.sale.close}</Button>
        </Card>
      </div>

      <h2 className="mb-3 mt-8 text-lg font-bold tracking-tight">{u.sale.todaySales}</h2>
      <Table head={[u.journal.time, u.sale.master, u.sale.client, u.sale.lines, u.common.total, ""]} empty={u.sale.noSales}>
        {todaySales.map((v) => (
          <Row key={v.id}>
            <Cell>{v.closedAt.slice(11)}</Cell>
            <Cell>{db.staff.find((s) => s.id === v.staffId)?.name}</Cell>
            <Cell>{db.clients.find((c) => c.id === v.clientId)?.name ?? "—"}</Cell>
            <Cell className="text-ink-soft">{v.lines.map((l) => l.name).join(", ")}</Cell>
            <Cell right>{fmtMoney(v.total)}</Cell>
            <Cell right>{v.refundedAt ? <Badge tone="bad">{u.sale.refunded}</Badge> : manage ? <ConfirmButton variant="ghost" onConfirm={() => refund(v)}>{u.sale.refund}</ConfirmButton> : null}</Cell>
          </Row>
        ))}
      </Table>
    </div>
  );
}
