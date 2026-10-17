"use client";

import { useState } from "react";
import { Segmented } from "@/components/ui";
import { useI18n } from "@/i18n/provider";
import { JournalScreen } from "./journal";
import { FlowScreen } from "./flow";

// Смешанный приём: журнал записи и живая очередь на одном экране, переключатель сверху.
export function MixedIntakeScreen() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"journal" | "flow">("journal");
  return (
    <div>
      <div className="mb-4">
        <Segmented value={tab} onChange={setTab} options={[{ value: "journal", label: t.u.flow.tabJournal }, { value: "flow", label: t.u.flow.tabFlow }]} />
      </div>
      <div key={tab} className="anim-fade-in">{tab === "journal" ? <JournalScreen /> : <FlowScreen />}</div>
    </div>
  );
}
