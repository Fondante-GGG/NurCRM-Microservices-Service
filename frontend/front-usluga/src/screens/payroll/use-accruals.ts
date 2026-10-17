"use client";

import { useMemo } from "react";
import { useStore } from "@/data/store";
import type { DB } from "@/data/sample/seed";
import type { Staff } from "@/data/types";
import { computeAccruals, type AccrualWithSteps } from "@/lib/payroll/calc";

export function closedOf(db: DB, period: string) {
  return db.closedPeriods.find((c) => c.period === period) ?? null;
}

// Закрытый месяц читается из снимка, открытый — считается заново по текущим данным.
export function accrualsFor(db: DB, period: string, staff: Staff[] = db.staff, live = false): AccrualWithSteps[] {
  const closed = live ? null : closedOf(db, period);
  if (closed) {
    const ids = new Set(staff.map((s) => s.id));
    return (closed.snapshot as AccrualWithSteps[]).filter((a) => ids.has(a.staffId));
  }
  return computeAccruals({ period, staff, schemes: db.schemes, services: db.services, visits: db.visits, appointments: db.appointments, adjustments: db.adjustments, shifts: db.shifts });
}

// Начисления за период с учётом выбранного филиала.
export function usePeriodAccruals(period: string): AccrualWithSteps[] {
  const { db, branchId } = useStore();
  return useMemo(() => accrualsFor(db, period).filter((a) => branchId === "all" || a.branchId === branchId), [db, period, branchId]);
}

export function periodRevenue(db: DB, period: string, branchId: string | "all"): number {
  return db.visits.filter((v) => v.closedAt.startsWith(period) && (branchId === "all" || v.branchId === branchId)).reduce((s, v) => s + v.total - v.refundAmount, 0);
}
