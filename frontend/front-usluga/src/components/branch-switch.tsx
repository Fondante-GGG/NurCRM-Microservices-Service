"use client";

import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { Icon } from "./icon";

// Переключатель филиала в шапке: владелец смотрит любую точку или всю сеть.
export function BranchSwitch() {
  const { db, branchId, setBranchId, ready } = useStore();
  const { t } = useI18n();
  if (!ready) return null;
  return (
    <label className="flex items-center gap-2 text-sm">
      <Icon name="pin" className="size-4 text-ink-soft" />
      <select
        value={branchId}
        onChange={(e) => setBranchId(e.target.value)}
        aria-label={t.u.common.branch}
        className="h-10 rounded-xl border border-line bg-card px-2.5 text-[13px] font-bold text-ink-mid outline-none focus:border-primary"
      >
        {db.branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
        <option value="all">{t.u.common.allBranches}</option>
      </select>
    </label>
  );
}
