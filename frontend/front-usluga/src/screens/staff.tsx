"use client";

import { useState } from "react";
import { Badge, Button, Cell, ConfirmButton, Drawer, Field, Input, PageHeader, Row, Segmented, Select, Table, Toggle } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import { ALL_PAGES, pagesOf, roleKind } from "@/data/sample/seed";
import { AccessLevelPicker } from "@/components/access-level";
import type { AccessMap, AccessRole, Staff } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { fmtMoney } from "@/lib/money";
import { MENU } from "@/lib/menu";

const COLORS = ["#0e7c86", "#2563eb", "#d97706", "#dc2626", "#16a34a", "#8b5cf6", "#db2777", "#64748b"];
const PAGES = MENU.usluga.flatMap((g) => g.items.map((i) => i.key));

export function StaffScreen() {
  const { db, update, branchId, role, canManage } = useStore();
  const manage = canManage("sotrudniki");
  const { t } = useI18n();
  const u = t.u;
  const [editing, setEditing] = useState<Staff | null>(null);
  const [tab, setTab] = useState<"profile" | "services" | "pay" | "access">("profile");
  const [rolesOpen, setRolesOpen] = useState(false);

  const list = db.staff.filter((s) => branchId === "all" || s.branchIds.includes(branchId));
  const posName = (id: string) => db.positions.find((p) => p.id === id)?.name ?? "";
  const roleName = (id: string) => db.roles.find((r) => r.id === id)?.name ?? "";
  const schemeName = (id: string | null) => db.schemes.find((s) => s.id === id)?.name ?? u.staff.noScheme;
  const accessRole = editing ? db.roles.find((r) => r.id === editing.roleId) : undefined;

  function openNew() {
    setTab("profile");
    const r = db.roles.find((x) => x.id === "r_master") ?? db.roles[db.roles.length - 1];
    setEditing({
      id: newId("u_"), name: "", phone: "", positionId: db.positions[0]?.id ?? "", branchIds: [branchId === "all" ? db.branches[0].id : branchId],
      role: roleKind(r), roleId: r.id, pages: null, access: null, employment: "contract", hiredAt: new Date().toISOString().slice(0, 10), active: true, schemeId: null, serviceIds: [], color: COLORS[db.staff.length % COLORS.length],
    });
  }
  function setRole(roleId: string) {
    if (!editing) return;
    setEditing({ ...editing, roleId, role: roleKind(db.roles.find((r) => r.id === roleId)), pages: null, access: null });
  }
  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => {
      const exists = d.staff.some((s) => s.id === editing.id);
      return { ...d, staff: exists ? d.staff.map((s) => (s.id === editing.id ? editing : s)) : [...d.staff, editing] };
    });
    setEditing(null);
  }

  const accessShown: AccessMap = editing ? (editing.access ?? accessRole?.access ?? {}) : {};
  const setLevel = (k: string, v: "view" | "manage" | null) => { if (!editing) return; const base = { ...(editing.access ?? accessRole?.access ?? {}) }; if (v) base[k] = v; else delete base[k]; setEditing({ ...editing, access: base, pages: pagesOf(base) }); };

  return (
    <div>
      <PageHeader title={u.staff.title} subtitle={u.staff.subtitle} actions={<>{role === "owner" && <Button onClick={() => setRolesOpen(true)}>{u.access.roles}</Button>}{manage && <Button variant="primary" onClick={openNew}>{u.common.add}</Button>}</>} />
      <Table head={[u.common.fullName, u.staff.position, u.staff.branches, u.access.role, u.staff.employment, u.staff.scheme, u.common.status]} empty={u.common.nothing}>
        {list.map((s) => (
          <Row key={s.id} onClick={() => { setTab("profile"); setEditing(s); }}>
            <Cell>
              <span className="flex items-center gap-2 font-semibold">
                <span className="size-2.5 rounded-full" style={{ background: s.color }} />
                {s.name}
              </span>
              <span className="text-xs text-ink-soft">{s.phone}</span>
            </Cell>
            <Cell className="whitespace-nowrap">{posName(s.positionId)}</Cell>
            <Cell className="text-ink-soft">{s.branchIds.length > 1 ? `${db.branches.find((x) => x.id === s.branchIds[0])?.name} +${s.branchIds.length - 1}` : db.branches.find((x) => x.id === s.branchIds[0])?.name}</Cell>
            <Cell className="whitespace-nowrap">{roleName(s.roleId)}{!db.settings.unifiedAccess && s.access && <Badge tone="info"> {u.access.individual}</Badge>}</Cell>
            <Cell className="whitespace-nowrap">{u.employment[s.employment]}</Cell>
            <Cell className="text-ink-soft"><span className="block max-w-56 truncate" title={schemeName(s.schemeId)}>{schemeName(s.schemeId)}</span></Cell>
            <Cell>{s.active ? <Badge tone="good">{u.common.active}</Badge> : <Badge>{u.common.inactive}</Badge>}</Cell>
          </Row>
        ))}
      </Table>

      <Drawer
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing && db.staff.some((s) => s.id === editing.id) ? editing.name : u.staff.newStaff}
        footer={
          <>
            <Button onClick={() => setEditing(null)}>{u.common.cancel}</Button>
            {manage && <Button variant="primary" onClick={save} disabled={!editing?.name.trim()}>{u.common.save}</Button>}
          </>
        }
      >
        {editing && (
          <div className="space-y-4">
            <Segmented value={tab} onChange={setTab} options={[{ value: "profile", label: u.staff.tabProfile }, { value: "services", label: u.staff.tabServices }, { value: "pay", label: u.staff.tabPay }, { value: "access", label: u.access.tabAccess }]} />
            {tab === "profile" && (
              <>
                <Field label={u.common.fullName}><Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
                <Field label={u.common.phone}><Input value={editing.phone} onChange={(e) => setEditing({ ...editing, phone: e.target.value })} /></Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label={u.staff.position}>
                    <Select value={editing.positionId} onChange={(e) => setEditing({ ...editing, positionId: e.target.value })}>
                      {db.positions.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </Select>
                  </Field>
                  <Field label={u.staff.hiredAt}><Input type="date" value={editing.hiredAt} onChange={(e) => setEditing({ ...editing, hiredAt: e.target.value })} /></Field>
                </div>
                <Field label={u.staff.color} group>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {COLORS.map((c) => (
                      <button key={c} type="button" aria-label={c} onClick={() => setEditing({ ...editing, color: c })} className={`press size-7 rounded-full border-2 ${editing.color === c ? "border-ink" : "border-transparent"}`} style={{ background: c }} />
                    ))}
                  </div>
                </Field>
                <Field label={u.staff.branches} group>
                  <div className="space-y-2 pt-1">
                    {db.branches.map((b) => (
                      <Toggle key={b.id} label={b.name} checked={editing.branchIds.includes(b.id)} onChange={(v) => setEditing({ ...editing, branchIds: v ? [...editing.branchIds, b.id] : editing.branchIds.filter((x) => x !== b.id) })} />
                    ))}
                  </div>
                </Field>
                <Toggle label={u.common.active} checked={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
              </>
            )}
            {tab === "services" && (
              <div className="space-y-2">
                {db.services.filter((s) => s.active).map((s) => (
                  <Toggle key={s.id} label={`${s.name} · ${fmtMoney(s.pricesByPosition[editing.positionId] ?? s.price)}`} checked={editing.serviceIds.includes(s.id)} onChange={(v) => setEditing({ ...editing, serviceIds: v ? [...editing.serviceIds, s.id] : editing.serviceIds.filter((x) => x !== s.id) })} />
                ))}
              </div>
            )}
            {tab === "pay" && (
              <div className="space-y-4">
                <Field label={u.staff.employment}>
                  <Select value={editing.employment} onChange={(e) => setEditing({ ...editing, employment: e.target.value as Staff["employment"] })}>
                    {(["staff", "contract", "self_employed", "rent"] as const).map((k) => <option key={k} value={k}>{u.employment[k]}</option>)}
                  </Select>
                </Field>
                <Field label={u.staff.scheme}>
                  <Select value={editing.schemeId ?? ""} onChange={(e) => setEditing({ ...editing, schemeId: e.target.value || null })}>
                    <option value="">{u.staff.noScheme}</option>
                    {db.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </Select>
                </Field>
              </div>
            )}
            {tab === "access" && (
              <div className="space-y-4">
                <Field label={u.access.role} hint={accessRole?.ownOnly ? u.access.ownOnlyHint : undefined}>
                  <Select value={editing.roleId} onChange={(e) => setRole(e.target.value)} disabled={role !== "owner" || editing.roleId === "r_owner"}>
                    {db.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                  </Select>
                </Field>
                {editing.roleId === "r_owner" ? (
                  <p className="text-sm text-ink-soft">{u.access.builtinHint}</p>
                ) : db.settings.unifiedAccess ? (
                  <div>
                    <div className="text-sm font-semibold">{u.access.pages}</div>
                    <p className="mt-1 text-xs text-ink-soft">{u.access.unifiedHint}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(accessShown).map(([k, lvl]) => <Badge key={k} tone={lvl === "manage" ? "info" : "neutral"}>{t.menu[k]} · {lvl === "manage" ? u.access.levelManage : u.access.levelView}</Badge>)}</div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold">{u.access.individual}</div>
                      {editing.access && <Button size="sm" variant="ghost" onClick={() => setEditing({ ...editing, pages: null, access: null })}>{u.access.asRole}</Button>}
                    </div>
                    <p className="mt-1 text-xs text-ink-soft">{u.access.levelHint}</p>
                    <div className="mt-2 divide-y divide-line-soft">
                      {PAGES.map((k) => (
                        <div key={k} className="flex items-center justify-between gap-3 py-2 text-sm"><span>{t.menu[k]}</span><AccessLevelPicker label={t.menu[k]} value={accessShown[k] ?? null} onChange={(v) => setLevel(k, v)} /></div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Drawer>

      <RolesDrawer open={rolesOpen} onClose={() => setRolesOpen(false)} />
    </div>
  );
}

// Роли доступа: список, создание, правка. Владелец и Администратор встроенные.
function RolesDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { db, update } = useStore();
  const { t } = useI18n();
  const u = t.u;
  const [editing, setEditing] = useState<AccessRole | null>(null);
  const [error, setError] = useState<string | null>(null);
  const usedBy = (id: string) => db.staff.filter((s) => s.roleId === id).length;

  function save() {
    if (!editing || !editing.name.trim()) return;
    update((d) => ({ ...d, roles: d.roles.some((r) => r.id === editing.id) ? d.roles.map((r) => (r.id === editing.id ? editing : r)) : [...d.roles, editing] }));
    setEditing(null);
  }
  function remove(r: AccessRole) {
    if (r.builtin) return;
    if (usedBy(r.id) > 0) { setError(u.access.inUse); return; }
    update((d) => ({ ...d, roles: d.roles.filter((x) => x.id !== r.id) }));
    setEditing(null);
  }

  return (
    <Drawer open={open} onClose={() => { setEditing(null); setError(null); onClose(); }} title={u.access.roles}
      footer={editing ? (
        <>
          {!editing.builtin && db.roles.some((r) => r.id === editing.id) && <ConfirmButton onConfirm={() => remove(editing)}>{u.common.delete}</ConfirmButton>}
          <span className="flex-1" />
          <Button onClick={() => { setEditing(null); setError(null); }}>{u.common.cancel}</Button>
          {!editing.builtin && <Button variant="primary" onClick={save} disabled={!editing.name.trim()}>{u.common.save}</Button>}
        </>
      ) : <Button variant="primary" onClick={() => setEditing({ id: newId("r_"), name: "", pages: ["zapisi", "klienty"], access: { zapisi: "manage", klienty: "view" }, builtin: false, ownOnly: true })}>{u.access.newRole}</Button>}>
      {error && <p className="mb-3 text-sm text-danger">{error}</p>}
      {!editing ? (
        <ul className="divide-y divide-line rounded-xl border border-line">
          {db.roles.map((r) => (
            <li key={r.id}>
              <button type="button" className="press flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-paper" onClick={() => { setError(null); setEditing(r); }}>
                <span>
                  <span className="font-semibold">{r.name}</span> {r.builtin && <Badge>{u.access.builtin}</Badge>} {r.ownOnly && <Badge tone="info">{u.access.ownOnly}</Badge>}
                  <span className="block text-xs text-ink-soft">{u.access.pages}: {r.id === "r_owner" ? u.common.all : `${Object.keys(r.access).length} (${u.access.levelManage.toLowerCase()}: ${Object.values(r.access).filter((x) => x === "manage").length})`} · {u.access.staffCount}: {usedBy(r.id)}</span>
                </span>
                <span className="text-ink-soft">›</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-4">
          {editing.builtin && <p className="rounded-lg bg-paper px-3 py-2 text-xs text-ink-soft">{u.access.builtinHint}</p>}
          <Field label={u.common.fullName}><Input value={editing.name} disabled={editing.builtin} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
          <div>
            <Toggle label={u.access.ownOnly} checked={editing.ownOnly} onChange={(v) => !editing.builtin && setEditing({ ...editing, ownOnly: v })} />
            <p className="mt-1 text-xs text-ink-soft">{u.access.ownOnlyHint}</p>
          </div>
          <Field label={u.access.pages} group>
            <div className="space-y-2 pt-1">
              {(editing.id === "r_owner" ? ALL_PAGES : PAGES).map((k) => (
                <Toggle key={k} label={t.menu[k]} checked={editing.pages.includes(k)} onChange={(v) => !editing.builtin && setEditing({ ...editing, pages: v ? [...editing.pages, k] : editing.pages.filter((x) => x !== k) })} />
              ))}
            </div>
          </Field>
        </div>
      )}
    </Drawer>
  );
}
