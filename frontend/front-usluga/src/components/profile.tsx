"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { periodOf, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";
import { accrualsFor } from "@/screens/payroll/use-accruals";
import { Button, Drawer, Field, Select } from "./ui";

function initials(name: string): string {
  return name.split(" ").slice(0, 2).map((w) => w[0] ?? "").join("").toUpperCase();
}

// Профиль вошедшего: кнопка в шапке и панель с короткой сводкой.
export function ProfileButton() {
  const { db, ready, user, role, userId, setUserId } = useStore();
  const { t } = useI18n();
  const p = t.u.profile;
  const [open, setOpen] = useState(false);
  const today = todayKey();
  const period = periodOf(today);

  const stats = useMemo(() => {
    if (!user) return [];
    const hired = new Date(user.hiredAt);
    const days = Math.max(0, Math.floor((new Date(today).getTime() - hired.getTime()) / 86400000));
    const tenure = days >= 60 ? `${Math.floor(days / 30)} ${p.months}` : `${days} ${p.days}`;
    const rows: { label: string; value: string }[] = [{ label: p.inCompany, value: `${tenure} (${p.since} ${user.hiredAt.split("-").reverse().join(".")})` }];
    if (role === "master") {
      const mine = db.visits.filter((v) => v.staffId === user.id && !v.refundedAt);
      const rev = mine.reduce((s, v) => s + v.total, 0);
      const earned = accrualsFor(db, period).filter((a) => a.staffId === user.id).reduce((s, a) => s + a.amount, 0);
      const shifts = db.shifts.filter((s) => s.staffId === user.id && s.date.startsWith(period) && s.date <= today && s.fact === "worked").length;
      rows.push({ label: p.visitsTotal, value: String(mine.length) }, { label: p.revenueTotal, value: fmtMoney(rev) }, { label: p.rating, value: fmtMoney(mine.length ? rev / mine.length : 0) }, { label: p.earnedMonth, value: fmtMoney(earned) }, { label: p.shiftsMonth, value: String(shifts) });
    } else if (role === "admin") {
      const made = db.appointments.filter((a) => a.createdById === user.id).length;
      const closed = db.visits.filter((v) => v.closedById === user.id);
      const earned = accrualsFor(db, period).filter((a) => a.staffId === user.id).reduce((s, a) => s + a.amount, 0);
      const shifts = db.shifts.filter((s) => s.staffId === user.id && s.date.startsWith(period) && s.date <= today && s.fact === "worked").length;
      rows.push({ label: p.bookingsMade, value: String(made) }, { label: p.visitsTotal, value: String(closed.length) }, { label: p.revenueTotal, value: fmtMoney(closed.reduce((s, v) => s + v.total - v.refundAmount, 0)) }, { label: p.earnedMonth, value: fmtMoney(earned) }, { label: p.shiftsMonth, value: String(shifts) });
    } else {
      const rev = db.visits.filter((v) => v.closedAt.startsWith(period)).reduce((s, v) => s + v.total - v.refundAmount, 0);
      rows.push({ label: p.companyRevenueMonth, value: fmtMoney(rev) }, { label: p.branchesCount, value: String(db.branches.length) }, { label: p.staffCount, value: String(db.staff.filter((s) => s.active && s.role !== "owner").length) });
    }
    return rows;
  }, [db, user, role, today, period, p]);

  if (!ready || !user) return null;
  const owner = db.staff.find((s) => s.roleId === "r_owner");
  const roleLabel = db.roles.find((r) => r.id === user.roleId)?.name ?? t.u.roles[role];

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="press flex h-10 items-center gap-2 rounded-xl border border-line bg-card py-1 pl-1 pr-3 text-left hover:bg-paper" aria-label={p.title}>
        <span className="flex size-7 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: user.color }}>{initials(user.name)}</span>
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-40 truncate text-sm font-semibold leading-tight">{user.name.split(" ")[0]}</span>
          <span className="block text-[11px] leading-tight text-ink-soft">{roleLabel}</span>
        </span>
      </button>

      <Drawer open={open} onClose={() => setOpen(false)} title={p.title}>
        <div className="flex items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-full text-lg font-bold text-white" style={{ background: user.color }}>{initials(user.name)}</span>
          <div>
            <div className="text-lg font-bold tracking-tight">{user.name}</div>
            <div className="text-sm text-ink-soft">{roleLabel} · {db.positions.find((x) => x.id === user.positionId)?.name} · {user.branchIds.map((b) => db.branches.find((x) => x.id === b)?.name).join(", ")}</div>
          </div>
        </div>
        <dl className="mt-5 divide-y divide-line rounded-xl border border-line">
          {stats.map((r) => (
            <div key={r.label} className="flex items-center justify-between gap-4 px-4 py-2.5 text-sm">
              <dt className="text-ink-soft">{r.label}</dt>
              <dd className="text-right font-semibold tabular-nums">{r.value}</dd>
            </div>
          ))}
        </dl>

        {(role === "owner" || userId !== owner?.id) && (
          <div className="mt-6 rounded-xl bg-paper p-4">
            <Field label={p.viewAs} hint={p.viewAsHint}>
              <Select value={userId} onChange={(e) => { setUserId(e.target.value); setOpen(false); }}>
                {db.staff.filter((s) => s.active).map((s) => <option key={s.id} value={s.id}>{s.name} · {db.roles.find((r) => r.id === s.roleId)?.name}</option>)}
              </Select>
            </Field>
            {role !== "owner" && owner && <Button size="sm" className="mt-3" onClick={() => { setUserId(owner.id); setOpen(false); }}>{p.backToOwner}</Button>}
          </div>
        )}
        {role === "owner" && (
          <Link href="/usluga/nastrojki" onClick={() => setOpen(false)} className="press mt-4 inline-flex rounded-lg border border-line px-3 py-2 text-sm font-semibold hover:bg-paper">{p.manageAccess}</Link>
        )}
      </Drawer>
    </>
  );
}
