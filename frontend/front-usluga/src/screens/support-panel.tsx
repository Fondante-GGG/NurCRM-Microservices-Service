"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, Cell, ConfirmButton, Drawer, Field, Input, PageHeader, Row, Segmented, Select, Table } from "@/components/ui";
import { newId, useStore } from "@/data/store";
import { CURRENT_COMPANY_ID } from "@/data/sample/seed";
import type { CompanyCard, SupportTicket } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, fmtDate, toIsoLocal, todayKey } from "@/lib/dates";
import { INDUSTRIES, INTAKE_MODES, PROFILES, type Industry, type IntakeMode } from "@/lib/industry";
import { LangSwitch } from "@/components/lang-switch";

type Tab = "companies" | "tickets" | "log";
const AGENT_DEFAULT = "Айдана";

export function SupportPanel() {
  const { db, update, ready, chooseIndustry, setSupportAgent, setUserId } = useStore();
  const { t, lang } = useI18n();
  const sp = t.u.sp;
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("companies");
  const [q, setQ] = useState("");
  const [agent, setAgent] = useState(AGENT_DEFAULT);
  const [openId, setOpenId] = useState<string | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [newBranch, setNewBranch] = useState<{ name: string; address: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const today = todayKey();

  // Текущая компания (та, что в кабинете) + примерные остальные.
  const self: CompanyCard = useMemo(() => ({
    id: CURRENT_COMPANY_ID, name: db.settings.company.name, phone: db.settings.company.phones, inn: db.settings.company.inn,
    industry: db.industry ?? "barber", intake: db.intake, branches: db.branches.length, staff: db.staff.filter((s) => s.active && s.role !== "owner").length,
    plan: "trial", lastLogin: `${today}T${new Date().toTimeString().slice(0, 5)}`, blocked: false, tempAccessUntil: db.tempAccessUntil,
  }), [db, today]);
  const companies = useMemo(() => [self, ...db.companies], [self, db.companies]);
  const shown = companies.filter((c) => !q || (c.name + c.phone + c.inn).toLowerCase().includes(q.toLowerCase()));
  const current = openId ? companies.find((c) => c.id === openId) ?? null : null;
  const isSelf = current?.id === CURRENT_COMPANY_ID;

  function log(companyId: string, action: string) {
    update((d) => ({ ...d, supportLog: [{ id: newId("sl"), at: toIsoLocal(new Date()), agent, companyId, action }, ...d.supportLog] }));
  }
  function patchCompany(id: string, patch: Partial<CompanyCard>) {
    update((d) => ({ ...d, companies: d.companies.map((c) => (c.id === id ? { ...c, ...patch } : c)) }));
  }
  function flash(msg: string) { setNotice(msg); window.setTimeout(() => setNotice(null), 3000); }

  function setIndustry(c: CompanyCard, i: Industry) {
    if (c.id === CURRENT_COMPANY_ID) chooseIndustry(i);
    else patchCompany(c.id, { industry: i, intake: PROFILES[i].defaultIntake });
    log(c.id, `${sp.changeIndustry}: ${t.u.industry.names[i]}`);
  }
  function setIntake(c: CompanyCard, m: IntakeMode) {
    if (c.id === CURRENT_COMPANY_ID) update((d) => ({ ...d, intake: m }));
    else patchCompany(c.id, { intake: m });
    log(c.id, `${sp.intakeMode}: ${t.u.industry.intakeModes[m]}`);
  }
  function grant(c: CompanyCard, on: boolean) {
    const until = on ? `${addDays(today, 3)}T${new Date().toTimeString().slice(0, 5)}` : null;
    if (c.id === CURRENT_COMPANY_ID) update((d) => ({ ...d, tempAccessUntil: until }));
    else patchCompany(c.id, { tempAccessUntil: until });
    log(c.id, on ? sp.grantAccess : sp.revokeAccess);
  }
  function addBranch(c: CompanyCard) {
    if (!newBranch || !newBranch.name.trim()) return;
    if (c.id === CURRENT_COMPANY_ID) update((d) => ({ ...d, branches: [...d.branches, { id: newId("b"), name: newBranch.name.trim(), address: newBranch.address.trim(), phone: "", hours: "", active: true, showcaseOnly: false }] }));
    else patchCompany(c.id, { branches: c.branches + 1 });
    log(c.id, `${sp.addBranch}: «${newBranch.name.trim()}»`);
    setNewBranch(null);
  }
  function removeBranch(bid: string, name: string) {
    update((d) => ({ ...d, branches: d.branches.filter((b) => b.id !== bid) }));
    log(CURRENT_COMPANY_ID, `${sp.removeBranch}: «${name}»`);
  }
  function loginAs(c: CompanyCard) {
    if (c.id !== CURRENT_COMPANY_ID) { flash(sp.onlyDemo); return; }
    log(c.id, sp.loginAs);
    setSupportAgent(agent);
    setUserId(db.staff.find((s) => s.roleId === "r_owner")?.id ?? "u_owner");
    router.push("/usluga/analitika");
  }

  // Обращения: текущей компании (без companyId) + возможные чужие.
  const tickets = db.support.map((x) => ({ ...x, companyId: x.companyId ?? CURRENT_COMPANY_ID }));
  const openTicket = ticketId ? tickets.find((x) => x.id === ticketId) ?? null : null;
  const companyName = (id: string) => companies.find((c) => c.id === id)?.name ?? id;
  function updateTicket(id: string, patch: Partial<SupportTicket>) {
    update((d) => ({ ...d, support: d.support.map((x) => (x.id === id ? { ...x, ...patch } : x)) }));
  }
  const tone = (s: SupportTicket["status"]) => (s === "done" ? "good" : s === "in_progress" ? "info" : "warn");

  if (!ready) return <main className="p-8 text-sm text-ink-soft">{t.u.common.loading}</main>;

  return (
    <main className="min-h-screen bg-paper">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-nav px-4 py-3 text-white sm:px-6">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-[10px] bg-gold text-base font-extrabold text-primary">N</span>
          <div><div className="text-[15px] font-bold leading-tight">{t.appName}</div><div className="text-[11px] text-nav-muted">{sp.title}</div></div>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-nav-text"><span>{sp.agent}</span><Input value={agent} onChange={(e) => setAgent(e.target.value)} className="h-9 w-32 text-ink" /></label>
          <LangSwitch />
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <PageHeader title={sp.title} subtitle={sp.subtitle} actions={<Segmented value={tab} onChange={setTab} options={(["companies", "tickets", "log"] as Tab[]).map((k) => ({ value: k, label: `${sp.tabs[k]}${k === "tickets" ? ` · ${tickets.filter((x) => x.status !== "done").length}` : ""}` }))} />} />
        {notice && <p className="anim-fade-in mb-3 rounded-xl bg-warn-soft px-4 py-2 text-sm font-bold text-warn">{notice}</p>}

        {tab === "companies" && (
          <>
            <div className="mb-3 max-w-md"><Input placeholder={sp.search} value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <Table head={[sp.company, sp.industry, sp.intake, sp.branches, sp.staff, sp.plan, sp.lastLogin, sp.tempAccess, t.u.common.status]} empty={t.u.common.nothing}>
              {shown.map((c) => (
                <Row key={c.id} onClick={() => { setOpenId(c.id); setNewBranch(null); }}>
                  <Cell><span className="font-bold">{c.name}</span>{c.id === CURRENT_COMPANY_ID && <span className="ml-2 whitespace-nowrap"><Badge tone="info">{sp.thisCompany}</Badge></span>}<span className="block whitespace-nowrap text-xs text-ink-soft">{c.phone}{c.inn ? ` · ИНН ${c.inn}` : ""}</span></Cell>
                  <Cell className="whitespace-nowrap">{t.u.industry.names[c.industry]}</Cell>
                  <Cell className="whitespace-nowrap text-ink-soft">{t.u.industry.intakeModes[c.intake]}</Cell>
                  <Cell right>{c.branches}</Cell>
                  <Cell right>{c.staff}</Cell>
                  <Cell><Badge tone={c.plan === "paid" ? "good" : c.plan === "trial" ? "info" : "neutral"}>{sp.plans[c.plan]}</Badge></Cell>
                  <Cell className="whitespace-nowrap text-ink-soft">{fmtDate(c.lastLogin.slice(0, 10), lang, { day: "numeric", month: "short" })} {c.lastLogin.slice(11)}</Cell>
                  <Cell>{c.tempAccessUntil ? <Badge tone="warn">{sp.tempAccessUntil} {fmtDate(c.tempAccessUntil.slice(0, 10), lang, { day: "numeric", month: "short" })}</Badge> : <span className="text-xs text-ink-soft">{sp.noTempAccess}</span>}</Cell>
                  <Cell>{c.blocked ? <Badge tone="bad">{sp.blocked}</Badge> : <Badge tone="good">{sp.active}</Badge>}</Cell>
                </Row>
              ))}
            </Table>
          </>
        )}

        {tab === "tickets" && (
          <Table head={[t.u.common.date, sp.company, t.u.support.topic, sp.ticketFrom, sp.tempAccess, t.u.common.status]} empty={sp.noTickets}>
            {tickets.sort((a, b) => (a.status === "done" ? 1 : 0) - (b.status === "done" ? 1 : 0) || b.createdAt.localeCompare(a.createdAt)).map((x) => (
              <Row key={x.id} onClick={() => { setTicketId(x.id); setReplyText(x.reply ?? ""); }}>
                <Cell className="whitespace-nowrap text-ink-soft">{fmtDate(x.createdAt.slice(0, 10), lang, { day: "numeric", month: "short" })} {x.createdAt.slice(11)}</Cell>
                <Cell className="font-bold">{companyName(x.companyId!)}</Cell>
                <Cell><span className="font-semibold">{t.u.support.topics[x.topic]}</span><span className="block max-w-md truncate text-xs text-ink-soft">{x.message}</span></Cell>
                <Cell className="text-ink-soft">{x.contact}</Cell>
                <Cell>{x.shareAccess ? <Badge tone="warn">{t.u.common.yes}</Badge> : <span className="text-xs text-ink-soft">{t.u.common.no}</span>}</Cell>
                <Cell><Badge tone={tone(x.status)}>{t.u.support.statuses[x.status]}</Badge>{x.assignee && <span className="ml-2 text-xs text-ink-soft">{x.assignee}</span>}</Cell>
              </Row>
            ))}
          </Table>
        )}

        {tab === "log" && (
          <Table head={[t.u.common.date, sp.who, sp.company, sp.what]} empty={sp.noLog}>
            {db.supportLog.map((e) => (
              <Row key={e.id}>
                <Cell className="whitespace-nowrap text-ink-soft">{fmtDate(e.at.slice(0, 10), lang, { day: "numeric", month: "short" })} {e.at.slice(11)}</Cell>
                <Cell className="font-bold">{e.agent}</Cell>
                <Cell>{companyName(e.companyId)}</Cell>
                <Cell>{e.action}</Cell>
              </Row>
            ))}
          </Table>
        )}
      </div>

      <Drawer open={!!current} onClose={() => setOpenId(null)} title={current?.name ?? ""} wide
        footer={current && <>
          <ConfirmButton onConfirm={() => { patchCompany(current.id, { blocked: !current.blocked }); log(current.id, current.blocked ? sp.unblock : sp.block); setOpenId(null); }}>{current.blocked ? sp.unblock : sp.block}</ConfirmButton>
          <span className="flex-1" />
          <Button onClick={() => { log(current.id, sp.resetPassword); flash(sp.resetPasswordDone); }}>{sp.resetPassword}</Button>
          <Button variant="primary" disabled={!current.tempAccessUntil} title={!current.tempAccessUntil ? sp.noAccessToLogin : undefined} onClick={() => loginAs(current)}>{sp.loginAs}</Button>
        </>}>
        {current && (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-3 text-sm">
              <div><div className="text-xs text-ink-soft">{t.u.common.phone}</div><div className="font-bold">{current.phone || "—"}</div></div>
              <div><div className="text-xs text-ink-soft">ИНН</div><div className="font-bold">{current.inn || "—"}</div></div>
              <div><div className="text-xs text-ink-soft">{sp.plan}</div><div className="font-bold">{sp.plans[current.plan]}</div></div>
            </div>

            <Card className="p-4">
              <div className="font-bold">{sp.tempAccess}</div>
              <p className="mt-1 text-xs text-ink-soft">{current.tempAccessUntil ? `${sp.tempAccessUntil} ${fmtDate(current.tempAccessUntil.slice(0, 10), lang, { day: "numeric", month: "long" })} ${current.tempAccessUntil.slice(11)}` : sp.noAccessToLogin}</p>
              <p className="mt-1 text-xs text-ink-soft">{sp.loginAsHint}</p>
              <div className="mt-3">{current.tempAccessUntil ? <Button size="sm" onClick={() => grant(current, false)}>{sp.revokeAccess}</Button> : <Button size="sm" variant="primary" onClick={() => grant(current, true)}>{sp.grantAccess}</Button>}</div>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={sp.changeIndustry} hint={sp.changeIndustryWarn}>
                <Select value={current.industry} onChange={(e) => setIndustry(current, e.target.value as Industry)}>
                  {INDUSTRIES.map((i) => <option key={i} value={i}>{t.u.industry.names[i]}</option>)}
                </Select>
              </Field>
              <Field label={sp.intakeMode} hint={PROFILES[current.industry].allowFlow ? t.u.industry.intakeHint : t.u.industry.intakeOnlyProcedure}>
                <Select value={current.intake} onChange={(e) => setIntake(current, e.target.value as IntakeMode)}>
                  {INTAKE_MODES.map((m) => <option key={m} value={m} disabled={m !== "schedule" && !PROFILES[current.industry].allowFlow}>{t.u.industry.intakeModes[m]}</option>)}
                </Select>
              </Field>
            </div>

            <Card className="p-4">
              <div className="flex items-center justify-between"><div className="font-bold">{t.u.branches.title} · {current.branches}</div>{!newBranch && <Button size="sm" variant="primary" onClick={() => setNewBranch({ name: "", address: "" })}>{sp.addBranch}</Button>}</div>
              {isSelf && (
                <ul className="mt-2 divide-y divide-line-soft text-sm">
                  {db.branches.map((b) => <li key={b.id} className="flex items-center justify-between gap-2 py-2"><span><span className="font-semibold">{b.name}</span><span className="block text-xs text-ink-soft">{b.address}</span></span>{db.branches.length > 1 && <ConfirmButton onConfirm={() => removeBranch(b.id, b.name)}>{sp.removeBranch}</ConfirmButton>}</li>)}
                </ul>
              )}
              {newBranch && (
                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                  <Field label={sp.branchName}><Input value={newBranch.name} onChange={(e) => setNewBranch({ ...newBranch, name: e.target.value })} /></Field>
                  <Field label={sp.branchAddress}><Input value={newBranch.address} onChange={(e) => setNewBranch({ ...newBranch, address: e.target.value })} /></Field>
                  <div className="flex items-end gap-2"><Button onClick={() => setNewBranch(null)}>{t.u.common.cancel}</Button><Button variant="primary" onClick={() => addBranch(current)} disabled={!newBranch.name.trim()}>{t.u.common.add}</Button></div>
                </div>
              )}
            </Card>
          </div>
        )}
      </Drawer>

      <Drawer open={!!openTicket} onClose={() => setTicketId(null)} title={openTicket ? `${t.u.support.topics[openTicket.topic]} · ${companyName(openTicket.companyId!)}` : ""}
        footer={openTicket && <>
          {openTicket.status === "new" && <Button onClick={() => updateTicket(openTicket.id, { status: "in_progress", assignee: agent })}>{sp.take}</Button>}
          <span className="flex-1" />
          <Button onClick={() => setTicketId(null)}>{t.u.common.close}</Button>
          {openTicket.status !== "done" && <Button variant="primary" onClick={() => { updateTicket(openTicket.id, { status: "done", reply: replyText.trim(), assignee: openTicket.assignee ?? agent }); if (openTicket.shareAccess) grant(companies.find((c) => c.id === openTicket.companyId)!, false); log(openTicket.companyId!, `${sp.close}: ${t.u.support.topics[openTicket.topic]}`); setTicketId(null); }}>{sp.close}</Button>}
        </>}>
        {openTicket && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2"><Badge tone={tone(openTicket.status)}>{t.u.support.statuses[openTicket.status]}</Badge><span className="text-xs text-ink-soft">{fmtDate(openTicket.createdAt.slice(0, 10), lang, { day: "numeric", month: "long" })} {openTicket.createdAt.slice(11)} · {openTicket.contact}</span>{openTicket.assignee && <span className="text-xs text-ink-soft">· {openTicket.assignee}</span>}</div>
            <p className="rounded-xl bg-paper p-4 leading-relaxed">{openTicket.message}</p>
            {openTicket.shareAccess && <p className="rounded-xl bg-warn-soft px-3 py-2 text-xs font-bold text-warn">{t.u.support.shareAccess}</p>}
            <Field label={sp.reply}><textarea rows={4} value={replyText} placeholder={sp.replyPlaceholder} onChange={(e) => setReplyText(e.target.value)} className="w-full rounded-xl border border-line-strong bg-card px-3.5 py-2.5 text-sm outline-none focus:border-primary" /></Field>
            {openTicket.reply && openTicket.status === "done" && <p className="text-xs text-ink-soft">{sp.reply}: {openTicket.reply}</p>}
          </div>
        )}
      </Drawer>
    </main>
  );
}
