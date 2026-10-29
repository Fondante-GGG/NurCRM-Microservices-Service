"use client";

import type { ComponentType } from "react";
import { PagePlaceholder } from "@/components/page-placeholder";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { StaffScreen } from "./staff";
import { ServicesScreen } from "./services";
import { BranchesScreen } from "./branches";
import { JournalScreen } from "./journal";
import { FlowScreen } from "./flow";
import { MixedIntakeScreen } from "./mixed-intake";
import { ClientsScreen } from "./clients";
import { SaleScreen } from "./sale";
import { CashScreen } from "./cash";
import { ShiftsScreen } from "./shifts";
import { PayrollScreen } from "./payroll";
import { AnalyticsScreen } from "./analytics";
import { HistoryScreen } from "./history";
import { RequestsScreen } from "./requests";
import { DocumentsScreen } from "./documents";
import { InventoryScreen } from "./inventory";
import { SettingsScreen } from "./settings";
import { BathInsideScreen } from "./banya/vnutri";
import { BathBarScreen } from "./banya/bar";
import { BathMasterServicesScreen } from "./banya/uslugi";
import { BathCheckoutScreen } from "./banya/vyhod";
import { CommercialChessboardScreen } from "./arenda/shahmatka";
import { CommercialReconciliationScreen } from "./arenda/sverka";

// Какой экран открывает каждый пункт меню «Услуги».
function ServicesTab() {
  return <ServicesScreen addons={false} />;
}

function DopServicesTab() {
  return <ServicesScreen addons={true} />;
}

const SCREENS: Record<string, ComponentType> = {
  sotrudniki: StaffScreen,
  uslugi: ServicesTab,
  "dop-uslugi": DopServicesTab,
  filialy: BranchesScreen,
  zapisi: JournalScreen,
  klienty: ClientsScreen,
  prodazha: SaleScreen,
  kassa: CashScreen,
  smeny: ShiftsScreen,
  zarplata: PayrollScreen,
  analitika: AnalyticsScreen,
  istoriya: HistoryScreen,
  zayavki: RequestsScreen,
  "dokumenty-klientov": DocumentsScreen,
  sklad: InventoryScreen,
  nastrojki: SettingsScreen,
  // Баня и сауна
  vnutri: BathInsideScreen,
  vhod: BathInsideScreen,
  bar: BathBarScreen,
  "uslugi-masterov": BathMasterServicesScreen,
  komnaty: JournalScreen,
  vyhod: BathCheckoutScreen,
  katalog: ServicesTab,
  // Аренда помещений
  shahmatka: CommercialChessboardScreen,
  arendatory: ClientsScreen,
  dogovory: DocumentsScreen,
  sverka: CommercialReconciliationScreen,
  rashody: CashScreen,
};

export function Screen({ page }: { page: string }) {
  const { ready, canSee, canManage, db } = useStore();
  const { t } = useI18n();
  const Cmp = page === "zapisi" && db.intake === "flow" ? FlowScreen : page === "zapisi" && db.intake === "mixed" ? MixedIntakeScreen : SCREENS[page];
  if (!Cmp) return <PagePlaceholder page={page} />;
  if (!ready) return <p className="text-sm text-ink-soft" aria-live="polite">{t.u.common.loading}</p>;
  if (!canSee(page)) {
    return (
      <div className="anim-rise max-w-md rounded-xl border border-dashed border-line px-5 py-10 text-center">
        <div className="font-semibold">{t.u.profile.noAccess}</div>
        <p className="mt-1 text-sm text-ink-soft">{t.u.profile.noAccessHint}</p>
      </div>
    );
  }
  return (
    <>
      {!canManage(page) && <p className="mb-4 rounded-xl bg-warn-soft px-4 py-2 text-sm font-semibold text-warn">{t.u.access.readOnly}</p>}
      <Cmp key={page} />
      <p className="mt-8 text-xs text-ink-soft">{t.u.common.demoNote}</p>
    </>
  );
}
