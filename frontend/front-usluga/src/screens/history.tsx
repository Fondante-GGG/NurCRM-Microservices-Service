"use client";

import { Badge, Cell, PageHeader, Row, Table } from "@/components/ui";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { fmtDate } from "@/lib/dates";

export function HistoryScreen() {
  const { db } = useStore();
  const { t, lang } = useI18n();
  const h = t.u.history;
  const fromSupport = db.supportLog.filter((e) => e.companyId === "c_self").map((e) => ({ id: e.id, at: e.at, staffId: null, entity: "support", entityId: e.id, action: "update" as const, summary: `${e.agent} (${t.u.settingsTabs.support}): ${e.action}` }));
  const list = [...db.audit, ...fromSupport].sort((a, b) => b.at.localeCompare(a.at));
  const ent = (e: string) => (h.entities as Record<string, string>)[e] ?? e;
  return (
    <div>
      <PageHeader title={h.title} subtitle={h.subtitle} />
      <Table head={[t.u.common.date, h.who, h.entity, h.what]} empty={t.u.common.nothing}>
        {list.map((a) => (
          <Row key={a.id}>
            <Cell className="whitespace-nowrap text-ink-soft">{fmtDate(a.at.slice(0, 10), lang, { day: "numeric", month: "short" })} {a.at.slice(11)}</Cell>
            <Cell>{db.staff.find((s) => s.id === a.staffId)?.name ?? (a.entity === "support" ? t.u.settingsTabs.support : "—")}</Cell>
            <Cell className="whitespace-nowrap"><Badge tone={a.action === "create" ? "good" : a.action === "delete" ? "bad" : "info"}>{ent(a.entity)}</Badge></Cell>
            <Cell>{a.summary}</Cell>
          </Row>
        ))}
      </Table>
    </div>
  );
}
