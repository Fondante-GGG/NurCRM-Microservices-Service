"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LangSwitch } from "@/components/lang-switch";
import { Button, Card, ConfirmButton, Field, Input, PageHeader, Segmented, Select, Toggle } from "@/components/ui";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { AUTH_ENABLED } from "@/lib/config";
import { MENU } from "@/lib/menu";
import { INTAKE_MODES, allowsFlow } from "@/lib/industry";
import { newId } from "@/data/store";
import { addDays, toIsoLocal, todayKey } from "@/lib/dates";
import type { ReminderSettings, SupportTicket } from "@/data/types";
import { AccessLevelPicker } from "@/components/access-level";
import { pagesOf } from "@/data/sample/seed";

type Tab = "company" | "journal" | "online" | "notifications" | "access" | "interface" | "security" | "equipment" | "support";
const TABS: Tab[] = ["company", "journal", "online", "notifications", "access", "interface", "security", "equipment", "support"];

// Настройки: вкладки слева, одна кнопка «Сохранить» внизу, появляется только при изменениях.
export function SettingsScreen() {
  const { db, update, reset, role } = useStore();
  const { t } = useI18n();
  const s = t.u.settings;
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tabParam = params.get("tab") as Tab | null;
  const tab: Tab = tabParam && TABS.includes(tabParam) ? tabParam : "company";
  const setTab = (next: Tab) => router.replace(`${pathname}?tab=${next}`, { scroll: false });

  const [form, setForm] = useState(db.settings);
  const [intake, setIntake] = useState(db.intake);
  const [ticket, setTicket] = useState<{ topic: SupportTicket["topic"]; message: string; contact: string; shareAccess: boolean; login: string; password: string }>({ topic: "setup", message: "", contact: "", shareAccess: false, login: "", password: "" });
  const [ticketSent, setTicketSent] = useState(false);
  const allowFlow = allowsFlow(db.industry);
  const [roles, setRoles] = useState(db.roles);
  const [notif, setNotif] = useState<boolean[]>(s.notifTypes.map(() => true));
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const bookingUrl = typeof window !== "undefined" ? `${window.location.origin}/booking` : "/booking";
  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(db.settings) || JSON.stringify(roles) !== JSON.stringify(db.roles) || intake !== db.intake, [form, roles, intake, db.settings, db.roles, db.intake]);
  const editableRoles = roles.filter((r) => r.id !== "r_owner");
  const visibleTabs = TABS.filter((k) => k !== "access" || role === "owner");

  useEffect(() => {
    if (!dirty) return;
    const onLeave = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [dirty]);

  async function save() {
    try {
      await fetch("/api/proxy/api/main/company/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.company.name,
          legal_name: form.company.legalName,
          inn: form.company.inn,
          okpo: form.company.okpo,
          account: form.company.account,
          bik: form.company.bik,
          address: form.company.address,
          phones: form.company.phones ? form.company.phones.split(",").map((p) => p.trim()).filter(Boolean) : [],
          intake,
        }),
      });
    } catch {}
    update((d) => ({ ...d, settings: form, intake, roles: roles.map((r) => (r.builtin ? d.roles.find((x) => x.id === r.id) ?? r : r)) }));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  }
  function discard() {
    setForm(db.settings);
    setRoles(db.roles);
    setIntake(db.intake);
  }
  async function sendTicket() {
    if (!ticket.message.trim() || !ticket.contact.trim()) return;
    try {
      await fetch("/api/proxy/api/main/support/tickets/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: ticket.topic,
          message: ticket.message.trim(),
          contact: ticket.contact.trim(),
          share_access: ticket.shareAccess,
        }),
      });
    } catch {}
    update((d) => ({ ...d, tempAccessUntil: ticket.shareAccess ? `${addDays(todayKey(), 3)}T${toIsoLocal(new Date()).slice(11)}` : d.tempAccessUntil, support: [{ id: newId("tk"), createdAt: toIsoLocal(new Date()), topic: ticket.topic, message: ticket.message.trim(), contact: ticket.contact.trim(), shareAccess: ticket.shareAccess, status: "new" }, ...d.support] }));
    setTicket({ topic: "setup", message: "", contact: "", shareAccess: false, login: "", password: "" });
    setTicketSent(true);
    window.setTimeout(() => setTicketSent(false), 4000);
  }
  const company = (patch: Partial<typeof form.company>) => setForm({ ...form, company: { ...form.company, ...patch } });
  const booking = (patch: Partial<typeof form.booking>) => setForm({ ...form, booking: { ...form.booking, ...patch } });
  const receipt = (patch: Partial<typeof form.receipt>) => setForm({ ...form, receipt: { ...form.receipt, ...patch } });

  return (
    <div className="pb-20">
      <PageHeader title={s.title} subtitle={s.subtitle} />
      <div className="grid gap-5 md:grid-cols-[220px_1fr]">
        <nav aria-label={s.title} className="flex gap-0.5 overflow-x-auto rounded-[14px] bg-segment p-1.5 md:flex-col md:self-start">
          {visibleTabs.map((k) => (
            <button key={k} type="button" onClick={() => setTab(k)} aria-current={tab === k ? "page" : undefined}
              className={`press whitespace-nowrap rounded-[10px] px-3 py-2.5 text-left text-[13px] ${tab === k ? "bg-card font-extrabold text-primary shadow-[0_1px_2px_rgba(16,24,40,.08)]" : "font-semibold text-ink-mid hover:bg-white/60"}`}>
              {t.u.settingsTabs[k]}
            </button>
          ))}
        </nav>

        <div key={tab} className="anim-fade-in min-w-0 space-y-4">
          {tab === "company" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.industry.current}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <span className="rounded-xl bg-primary px-4 py-2 text-sm font-extrabold text-white">{db.industry ? t.u.industry.names[db.industry] : "—"}</span>
                </div>
                <div className="mt-5">
                  <Field label={t.u.industry.intake} hint={allowFlow ? t.u.industry.intakeHint : t.u.industry.intakeOnlyProcedure} group>
                    <div className="inline-flex rounded-xl bg-segment p-1">
                      {INTAKE_MODES.map((m) => (
                        <button key={m} type="button" disabled={m !== "schedule" && !allowFlow} onClick={() => setIntake(m)} aria-pressed={intake === m} className={`press rounded-[10px] px-3.5 py-2 text-[13px] font-bold disabled:opacity-40 ${intake === m ? "bg-card text-primary shadow-[0_1px_2px_rgba(16,24,40,.08)]" : "text-[#475467]"}`}>{t.u.industry.intakeModes[m]}</button>
                      ))}
                    </div>
                  </Field>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.company.main}</h2>
                <p className="mt-1 text-xs text-ink-soft">{t.u.company.requisitesHint}</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field label={t.u.company.name}><Input value={form.company.name} onChange={(e) => company({ name: e.target.value })} /></Field>
                  <Field label={t.u.company.legalName}><Input value={form.company.legalName} onChange={(e) => company({ legalName: e.target.value })} /></Field>
                  <Field label={t.u.company.inn}><Input value={form.company.inn} inputMode="numeric" onChange={(e) => company({ inn: e.target.value })} /></Field>
                  <Field label={t.u.company.okpo}><Input value={form.company.okpo} inputMode="numeric" onChange={(e) => company({ okpo: e.target.value })} /></Field>
                  <Field label={t.u.company.account}><Input value={form.company.account} inputMode="numeric" onChange={(e) => company({ account: e.target.value })} /></Field>
                  <Field label={t.u.company.bik}><Input value={form.company.bik} inputMode="numeric" onChange={(e) => company({ bik: e.target.value })} /></Field>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.company.contacts}</h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field label={t.u.company.address}><Input value={form.company.address} onChange={(e) => company({ address: e.target.value })} /></Field>
                  <Field label={t.u.company.phones} hint={t.u.company.phonesHint}><Input value={form.company.phones} inputMode="tel" onChange={(e) => company({ phones: e.target.value })} /></Field>
                </div>
              </Card>
            </>
          )}

          {tab === "journal" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">{s.journal}</h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  <Field label={s.workFrom}><Input type="time" value={form.workFrom} onChange={(e) => setForm({ ...form, workFrom: e.target.value })} /></Field>
                  <Field label={s.workTo}><Input type="time" value={form.workTo} onChange={(e) => setForm({ ...form, workTo: e.target.value })} /></Field>
                  <Field label={s.slot}><Input type="number" min={5} step={5} value={form.slotMin} onChange={(e) => setForm({ ...form, slotMin: Number(e.target.value) || 15 })} /></Field>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{s.payroll}</h2>
                <div className="mt-3 max-w-xs"><Field label={s.fotThreshold} hint={s.fotHint}><Input type="number" min={0} max={100} value={form.fotThreshold} onChange={(e) => setForm({ ...form, fotThreshold: Number(e.target.value) || 0 })} /></Field></div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.cash.title}</h2>
                <div className="mt-3 max-w-xs"><Field label={t.u.approval.limit} hint={t.u.approval.limitHint}><Input type="number" min={0} step={1000} value={form.approvalLimit} onChange={(e) => setForm({ ...form, approvalLimit: Math.max(0, Number(e.target.value) || 0) })} /></Field></div>
              </Card>
            </>
          )}

          {tab === "online" && (
            <Card className="p-5">
              <h2 className="font-bold">{t.u.booking.settingsTitle}</h2>
              <p className="mt-1 text-xs text-ink-soft">{t.u.booking.settingsHint}</p>
              <div className="mt-3 space-y-3">
                <Toggle label={t.u.booking.enabled} checked={form.booking.enabled} onChange={(v) => booking({ enabled: v })} />
                <Field label={t.u.booking.link} group>
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="rounded-lg bg-paper px-3 py-2 text-sm">{bookingUrl}</code>
                    <a href="/booking" target="_blank" rel="noreferrer" className="press rounded-lg border border-line px-3 py-1.5 text-sm font-semibold hover:bg-paper">{t.u.booking.open}</a>
                    <Button size="sm" onClick={() => { try { navigator.clipboard.writeText(bookingUrl); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch {} }}>{copied ? t.u.booking.copied : t.u.booking.copy}</Button>
                  </div>
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label={t.u.booking.title}><Input value={form.booking.title} onChange={(e) => booking({ title: e.target.value })} /></Field>
                  <Field label={t.u.booking.intro}><Input value={form.booking.intro} onChange={(e) => booking({ intro: e.target.value })} /></Field>
                  <Field label={t.u.booking.slotMin}><Input type="number" min={5} step={5} value={form.booking.slotMin} onChange={(e) => booking({ slotMin: Number(e.target.value) || 30 })} /></Field>
                  <Field label={t.u.booking.leadHours}><Input type="number" min={0} value={form.booking.leadHours} onChange={(e) => booking({ leadHours: Number(e.target.value) || 0 })} /></Field>
                  <Field label={t.u.booking.maxDays}><Input type="number" min={1} max={60} value={form.booking.maxDays} onChange={(e) => booking({ maxDays: Math.min(60, Math.max(1, Number(e.target.value) || 14)) })} /></Field>
                </div>
                <Toggle label={t.u.booking.showPrices} checked={form.booking.showPrices} onChange={(v) => booking({ showPrices: v })} />
                <Toggle label={t.u.booking.chooseMaster} checked={form.booking.chooseMaster} onChange={(v) => booking({ chooseMaster: v })} />
              </div>
            </Card>
          )}

          {tab === "notifications" && (
            <>
            <RemindersCard value={form.reminders} onChange={(reminders) => setForm({ ...form, reminders })} />
            <Card className="p-5">
              <h2 className="font-bold">{s.notifications}</h2>
              <p className="mt-1 text-xs text-ink-soft">{s.notifHint}</p>
              <div className="mt-3 space-y-2">
                {s.notifTypes.map((n, i) => <Toggle key={n} label={n} checked={notif[i]} onChange={(v) => setNotif(notif.map((x, j) => (j === i ? v : x)))} />)}
              </div>
            </Card>
            </>
          )}

          {tab === "access" && role === "owner" && (
            <Card className="p-5">
              <h2 className="font-bold">{t.u.access.title}</h2>
              <div className="mt-3">
                <Toggle label={t.u.access.unified} checked={form.unifiedAccess} onChange={(v) => setForm({ ...form, unifiedAccess: v })} />
                <p className="mt-1 text-xs text-ink-soft">{t.u.access.unifiedHint}</p>
              </div>
              {form.unifiedAccess ? (
                <>
                  <p className="mt-4 text-xs text-ink-soft">{t.u.access.hint} {t.u.access.levelHint}</p>
                  <div className="overflow-x-auto">
                    <table className="mt-2 w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-ink-soft">
                          <th className="py-1 font-semibold">{t.u.access.section}</th>
                          {editableRoles.map((r) => <th key={r.id} className="py-1 text-center font-semibold">{r.name}{r.builtin && <span className="block text-[10px] font-normal">{t.u.access.builtin}</span>}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {MENU.usluga.flatMap((g) => g.items).map((item) => (
                          <tr key={item.key} className="border-t border-line">
                            <td className="py-2 font-semibold">{t.menu[item.key]}</td>
                            {editableRoles.map((r) => (
                              <td key={r.id} className="py-1.5 text-center">
                                <AccessLevelPicker compact={editableRoles.length > 2} label={`${t.menu[item.key]} · ${r.name}`} disabled={r.builtin} value={roles.find((x) => x.id === r.id)!.access[item.key] ?? null} onChange={(v) => setRoles(roles.map((x) => { if (x.id !== r.id) return x; const access = { ...x.access }; if (v) access[item.key] = v; else delete access[item.key]; return { ...x, access, pages: pagesOf(access) }; }))} />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-2 text-xs text-ink-soft">{t.u.access.builtinHint}</p>
                </>
              ) : (
                <p className="mt-4 text-sm text-ink-soft">{t.u.access.perStaff}</p>
              )}
            </Card>
          )}

          {tab === "interface" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.access.language}</h2>
                <p className="mt-1 text-xs text-ink-soft">{t.u.access.languageHint}</p>
                <div className="mt-3"><LangSwitch /></div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{s.demo}</h2>
                <p className="mt-1 text-sm text-ink-soft">{s.resetHint}</p>
                <ConfirmButton size="md" className="mt-3" onConfirm={reset}>{t.u.common.resetDemo}</ConfirmButton>
              </Card>
            </>
          )}

          {tab === "security" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.security.title}</h2>
                <p className="mt-1 text-xs text-ink-soft">{t.u.security.hint}</p>
                <div className="mt-3 grid max-w-md gap-3">
                  <Field label={t.u.security.oldPassword}><Input type="password" autoComplete="current-password" disabled={!AUTH_ENABLED} /></Field>
                  <Field label={t.u.security.newPassword}><Input type="password" autoComplete="new-password" disabled={!AUTH_ENABLED} /></Field>
                  <Field label={t.u.security.repeat}><Input type="password" autoComplete="new-password" disabled={!AUTH_ENABLED} /></Field>
                  <div><Button disabled={!AUTH_ENABLED}>{t.u.security.change}</Button></div>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.security.sessions}</h2>
                <p className="mt-1 text-sm text-ink-soft">{t.u.security.sessionsHint}</p>
                {AUTH_ENABLED && (
                  <form action="/api/auth/logout" method="post" className="mt-3"><Button variant="danger" type="submit">{t.u.security.logout}</Button></form>
                )}
              </Card>
            </>
          )}

          {tab === "support" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.support.title}</h2>
                <p className="mt-1 text-xs text-ink-soft">{t.u.support.hint}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a href="tel:+996700000000" className="press inline-flex h-10 items-center gap-2 rounded-xl border-[1.5px] border-line-strong px-4 text-sm font-bold text-ink-mid hover:bg-paper">{t.u.support.phone}: +996 700 000 000</a>
                  <a href="https://t.me/nurcrm_support" target="_blank" rel="noreferrer" className="press inline-flex h-10 items-center gap-2 rounded-xl border-[1.5px] border-line-strong px-4 text-sm font-bold text-ink-mid hover:bg-paper">{t.u.support.telegram}</a>
                  <a href="https://wa.me/996700000000" target="_blank" rel="noreferrer" className="press inline-flex h-10 items-center gap-2 rounded-xl border-[1.5px] border-line-strong px-4 text-sm font-bold text-ink-mid hover:bg-paper">{t.u.support.whatsapp}</a>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="font-bold">{t.u.support.newTicket}</h2>
                {ticketSent && <p className="anim-fade-in mt-2 rounded-xl bg-positive-soft px-3 py-2 text-sm font-bold text-positive">{t.u.support.sent}</p>}
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Field label={t.u.support.topic}>
                    <Select value={ticket.topic} onChange={(e) => setTicket({ ...ticket, topic: e.target.value as SupportTicket["topic"] })}>
                      {(["industry", "setup", "bug", "other"] as const).map((k) => <option key={k} value={k}>{t.u.support.topics[k]}</option>)}
                    </Select>
                  </Field>
                  <Field label={t.u.support.contact} hint={t.u.support.contactHint}><Input value={ticket.contact} inputMode="tel" onChange={(e) => setTicket({ ...ticket, contact: e.target.value })} /></Field>
                </div>
                <div className="mt-3"><Field label={t.u.support.message}><textarea value={ticket.message} onChange={(e) => setTicket({ ...ticket, message: e.target.value })} rows={4} className="w-full rounded-xl border border-line-strong bg-card px-3.5 py-2.5 text-sm outline-none focus:border-primary" /></Field></div>
                <div className="mt-4">
                  <Toggle label={t.u.support.shareAccess} checked={ticket.shareAccess} onChange={(v) => setTicket({ ...ticket, shareAccess: v })} />
                  <p className="mt-1 text-xs text-ink-soft">{t.u.support.shareAccessHint}</p>
                </div>
                <Button variant="primary" className="mt-4" onClick={sendTicket} disabled={!ticket.message.trim() || !ticket.contact.trim()}>{t.u.support.send}</Button>
              </Card>
              {db.tempAccessUntil && (
                <Card className="p-5">
                  <h2 className="font-bold">{t.u.sp.tempAccess}</h2>
                  <p className="mt-1 text-sm text-ink-soft">{t.u.support.shareAccessHint} {t.u.sp.tempAccessUntil} {db.tempAccessUntil.slice(0, 10).split("-").reverse().join(".")} {db.tempAccessUntil.slice(11)}.</p>
                  <Button variant="danger" className="mt-3" onClick={() => update((d) => ({ ...d, tempAccessUntil: null }))}>{t.u.sp.revokeAccess}</Button>
                </Card>
              )}
              <Card className="p-5">
                <h2 className="font-bold">{t.u.support.history}</h2>
                {db.support.length === 0 ? <p className="mt-2 text-sm text-ink-soft">{t.u.support.none}</p> : (
                  <ul className="mt-3 divide-y divide-line-soft">
                    {db.support.map((x) => (
                      <li key={x.id} className="flex flex-wrap items-start justify-between gap-2 py-2.5 text-sm">
                        <span><span className="font-bold">{t.u.support.topics[x.topic]}</span><span className="block text-ink-soft">{x.message}</span><span className="block text-xs text-ink-soft">{x.createdAt.slice(0, 10).split("-").reverse().join(".")} {x.createdAt.slice(11)} · {x.contact}{x.shareAccess ? ` · ${t.u.support.shareAccess}` : ""}</span></span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${x.status === "done" ? "bg-positive-soft text-positive" : x.status === "in_progress" ? "bg-gold-soft text-primary" : "bg-warn-soft text-warn"}`}>{t.u.support.statuses[x.status]}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          )}

          {tab === "equipment" && (
            <Card className="p-5">
              <h2 className="font-bold">{t.u.equipment.title}</h2>
              <p className="mt-1 text-xs text-ink-soft">{t.u.equipment.hint}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Field label={t.u.equipment.connection}>
                  <Select value={form.receipt.connection} onChange={(e) => receipt({ connection: e.target.value as typeof form.receipt.connection })}>
                    {(["none", "usb", "network", "bluetooth"] as const).map((k) => <option key={k} value={k}>{t.u.equipment.connections[k]}</option>)}
                  </Select>
                </Field>
                <Field label={t.u.equipment.paperWidth}>
                  <Select value={form.receipt.paperWidth} onChange={(e) => receipt({ paperWidth: Number(e.target.value) === 58 ? 58 : 80 })}>
                    <option value={58}>58 мм</option>
                    <option value={80}>80 мм</option>
                  </Select>
                </Field>
                {form.receipt.connection !== "none" && (
                  <>
                    <Field label={t.u.equipment.model} hint={t.u.equipment.modelHint}><Input value={form.receipt.model} onChange={(e) => receipt({ model: e.target.value })} /></Field>
                    {form.receipt.connection !== "usb" && <Field label={t.u.equipment.address} hint={t.u.equipment.addressHint}><Input value={form.receipt.address} onChange={(e) => receipt({ address: e.target.value })} /></Field>}
                  </>
                )}
              </div>
              <div className="mt-4 space-y-2">
                <Toggle label={t.u.equipment.autoPrint} checked={form.receipt.autoPrint} onChange={(v) => receipt({ autoPrint: v })} />
                <Toggle label={t.u.equipment.printLogo} checked={form.receipt.printLogo} onChange={(v) => receipt({ printLogo: v })} />
              </div>
              <div className="mt-4 max-w-md"><Field label={t.u.equipment.footer}><Input value={form.receipt.footer} onChange={(e) => receipt({ footer: e.target.value })} /></Field></div>
              <div className="mt-4 flex items-center gap-3">
                <Button disabled={form.receipt.connection === "none"} title={t.u.equipment.testHint}>{t.u.equipment.test}</Button>
                <span className="text-xs text-ink-soft">{t.u.equipment.testHint}</span>
              </div>
            </Card>
          )}
        </div>
      </div>

      {(dirty || saved) && (
        <div className="anim-rise fixed inset-x-0 bottom-6 z-30 flex justify-center px-4 md:left-64">
          <div role="status" aria-live="polite" className={`flex w-full max-w-2xl flex-wrap items-center gap-3 rounded-2xl px-5 py-4 shadow-[0_12px_32px_rgba(11,42,60,.28)] ${saved ? "bg-positive text-white" : "bg-primary text-white"}`}>
            <span className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${saved ? "bg-white/20" : "bg-gold text-primary"}`}>
              {saved ? "✓" : "!"}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-base font-extrabold">{saved ? s.saved : t.u.settingsCommon.unsaved}</span>
              {!saved && <span className="block text-sm text-white/80">{t.u.settingsCommon.unsavedHint}</span>}
            </span>
            {dirty && (
              <span className="flex gap-2">
                <button type="button" onClick={discard} className="press h-11 rounded-xl border-[1.5px] border-white/40 px-4 text-sm font-bold text-white hover:bg-white/10">{t.u.settingsCommon.discard}</button>
                <Button variant="primary" onClick={save}>{t.u.common.save}</Button>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Напоминания клиентам: за сколько часов, канал и текст с подстановками, живой пример сообщения.
function RemindersCard({ value, onChange }: { value: ReminderSettings; onChange: (v: ReminderSettings) => void }) {
  const { db } = useStore();
  const { t } = useI18n();
  const r = t.u.reminders;
  const OPTIONS = [48, 24, 12, 3, 2, 1];
  const master = db.staff.find((x) => x.role === "master")?.name.split(" ")[0] ?? "";
  const preview = value.template
    .replaceAll("{имя}", db.clients[0]?.name.split(" ")[0] ?? "Азамат")
    .replaceAll("{дата}", "18.10")
    .replaceAll("{время}", "15:30")
    .replaceAll("{мастер}", master)
    .replaceAll("{адрес}", db.branches[0]?.address ?? "");
  return (
    <Card className="p-5">
      <h2 className="font-bold">{r.title}</h2>
      <p className="mt-1 text-xs text-ink-soft">{r.hint}</p>
      <div className="mt-3"><Toggle label={r.enabled} checked={value.enabled} onChange={(v) => onChange({ ...value, enabled: v })} /></div>
      <div className={`mt-4 space-y-4 ${value.enabled ? "" : "pointer-events-none opacity-50"}`}>
        <Field label={r.hoursBefore} group>
          <div className="flex flex-wrap gap-2">
            {OPTIONS.map((h) => {
              const on = value.hoursBefore.includes(h);
              return <button key={h} type="button" aria-pressed={on} onClick={() => onChange({ ...value, hoursBefore: on ? value.hoursBefore.filter((x) => x !== h) : [...value.hoursBefore, h].sort((a, b) => b - a) })} className={`press rounded-xl border px-3 py-1.5 text-sm font-bold ${on ? "border-gold bg-gold-soft" : "border-line bg-card text-ink-soft"}`}>{h} {r.hours}</button>;
            })}
          </div>
        </Field>
        <Field label={r.channel} group>
          <Segmented value={value.channel} onChange={(c) => onChange({ ...value, channel: c })} options={(["whatsapp", "sms", "telegram"] as const).map((c) => ({ value: c, label: r.channels[c] }))} />
        </Field>
        <Field label={r.template} hint={r.templateHint}>
          <textarea value={value.template} onChange={(e) => onChange({ ...value, template: e.target.value })} rows={3} className="w-full rounded-xl border border-line-strong bg-card px-3 py-2 text-sm outline-none focus:border-primary" />
        </Field>
        <div>
          <div className="mb-1 text-xs font-semibold text-ink-soft">{r.preview}</div>
          <div className="max-w-md rounded-2xl rounded-tl-sm bg-positive-soft px-4 py-3 text-sm">{preview}</div>
        </div>
      </div>
    </Card>
  );
}
