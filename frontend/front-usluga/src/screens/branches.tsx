"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, Drawer, Field, Input, PageHeader, Toggle } from "@/components/ui";
import { useStore } from "@/data/store";
import type { Branch } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { periodOf, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

export function BranchesScreen() {
  const { db, update, canManage } = useStore();
  const manage = canManage("filialy");
  const { t } = useI18n();
  const u = t.u;
  const [editing, setEditing] = useState<Branch | null>(null);
  const [askSupport, setAskSupport] = useState(false);
  const router = useRouter();
  const period = periodOf(todayKey());

  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, branches: d.branches.some((b) => b.id === editing.id) ? d.branches.map((b) => (b.id === editing.id ? editing : b)) : [...d.branches, editing] }));
    setEditing(null);
  }

  return (
    <div>
      <PageHeader title={u.branches.title} subtitle={u.branches.subtitle} actions={manage ? <Button variant="primary" onClick={() => setAskSupport(true)}>{u.common.add}</Button> : undefined} />
      <div className="grid gap-4 md:grid-cols-2">
        {db.branches.map((b) => {
          const masters = db.staff.filter((s) => s.role === "master" && s.active && s.branchIds.includes(b.id)).length;
          const revenue = db.visits.filter((v) => v.branchId === b.id && v.closedAt.startsWith(period)).reduce((s, v) => s + v.total - v.refundAmount, 0);
          return (
            <Card key={b.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold tracking-tight">{b.name}</h2>
                  <p className="mt-1 text-sm text-ink-soft">{b.address}</p>
                  <p className="text-sm text-ink-soft">{b.phone} · {b.hours}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  {b.showcaseOnly ? <span className="whitespace-nowrap"><Badge tone="info">{u.branches.showcaseBadge}</Badge></span> : b.active ? <Badge tone="good">{u.common.active}</Badge> : <Badge>{u.common.inactive}</Badge>}
                </div>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-ink-soft">{u.branches.masters}</dt><dd className="font-semibold">{masters}</dd></div>
                <div><dt className="text-xs text-ink-soft">{u.branches.revenueMonth}</dt><dd className="font-semibold">{fmtMoney(revenue)}</dd></div>
              </dl>
              <div className="mt-4"><Button size="sm" onClick={() => setEditing(b)}>{u.common.edit}</Button></div>
            </Card>
          );
        })}
      </div>

      <Drawer open={askSupport} onClose={() => setAskSupport(false)} title={u.branches.viaSupport}
        footer={<><Button onClick={() => setAskSupport(false)}>{u.common.close}</Button><Button variant="primary" onClick={() => { setAskSupport(false); router.push("/usluga/nastrojki?tab=support"); }}>{u.branches.goSupport}</Button></>}>
        <div className="rounded-2xl bg-gold-soft p-5">
          <div className="flex size-11 items-center justify-center rounded-xl bg-gold text-primary text-xl font-extrabold">!</div>
          <p className="mt-3 text-sm leading-relaxed">{u.branches.viaSupportText}</p>
        </div>
      </Drawer>

      <Drawer open={!!editing} onClose={() => setEditing(null)} title={editing && db.branches.some((b) => b.id === editing.id) ? editing.name : u.branches.newBranch}
        footer={<><Button onClick={() => setEditing(null)}>{u.common.cancel}</Button>{manage && <Button variant="primary" onClick={save} disabled={!editing?.name.trim()}>{u.common.save}</Button>}</>}>
        {editing && (
          <div className="space-y-4">
            <Field label={u.common.name}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
            <Field label={u.common.address}><Input value={editing.address} onChange={(e) => setEditing({ ...editing, address: e.target.value })} /></Field>
            <Field label={u.common.phone}><Input value={editing.phone} onChange={(e) => setEditing({ ...editing, phone: e.target.value })} /></Field>
            <Field label={u.branches.hours}><Input value={editing.hours} onChange={(e) => setEditing({ ...editing, hours: e.target.value })} /></Field>
            <Toggle label={u.common.active} checked={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
            <div>
              <Toggle label={u.branches.showcaseOnly} checked={editing.showcaseOnly} onChange={(v) => setEditing({ ...editing, showcaseOnly: v })} />
              <p className="mt-1 pl-13 text-xs text-ink-soft">{u.branches.showcaseHint}</p>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
