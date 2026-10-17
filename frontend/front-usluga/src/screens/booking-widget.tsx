"use client";

import { useMemo, useState } from "react";
import { Icon } from "@/components/icon";
import { newId, useStore } from "@/data/store";
import type { Service, Staff } from "@/data/types";
import { useI18n } from "@/i18n/provider";
import { addDays, fmtDate, hhmmOf, minutesOf, parseIso, toIsoLocal, todayKey } from "@/lib/dates";
import { fmtMoney } from "@/lib/money";

type Step = "start" | "services" | "master" | "time" | "contacts" | "done";
const ORDER: Step[] = ["services", "master", "time", "contacts", "done"];

function initials(name: string): string {
  return name.split(" ").slice(0, 2).map((w) => w[0] ?? "").join("").toUpperCase();
}

export function BookingWidget() {
  const { db, ready, update } = useStore();
  const { t } = useI18n();
  const b = t.u.booking;
  const cfg = db.settings.booking;
  const [step, setStep] = useState<Step>("start");
  const [firstMaster, setFirstMaster] = useState(false);
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [staffId, setStaffId] = useState<string | null>(null); // null = любой
  const [date, setDate] = useState(todayKey());
  const [time, setTime] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [comment, setComment] = useState("");
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string | null>(null);

  const branches = db.branches.filter((x) => x.active && !x.showcaseOnly);
  const [branchId, setBranchId] = useState<string>("");
  const branch = branches.find((x) => x.id === branchId) ?? branches[0];
  const masters = useMemo(() => db.staff.filter((s) => s.role === "master" && s.active && branch && s.branchIds.includes(branch.id)), [db.staff, branch]);
  const services = db.services.filter((s) => s.active && s.online && masters.some((m) => m.serviceIds.includes(s.id)));
  const shown = services.filter((s) => (!cat || s.categoryId === cat) && (!query || s.name.toLowerCase().includes(query.toLowerCase())));
  const cats = db.categories.filter((c) => services.some((s) => s.categoryId === c.id));
  const chosen = serviceIds.map((id) => db.services.find((s) => s.id === id)!).filter(Boolean);
  const duration = chosen.reduce((s, x) => s + x.duration, 0);
  const priceFor = (s: Service, m?: Staff | null) => (m ? s.pricesByPosition[m.positionId] ?? s.price : s.price);
  const master = staffId ? db.staff.find((s) => s.id === staffId) ?? null : null;
  const total = chosen.reduce((s, x) => s + priceFor(x, master), 0);
  const candidates = masters.filter((m) => serviceIds.every((id) => m.serviceIds.includes(id)));

  // Свободные слоты: по смене мастера, шагу и уже стоящим записям.
  function slotsFor(m: Staff, d: string): string[] {
    const sh = db.shifts.find((x) => x.staffId === m.id && x.date === d && x.fact !== "missed");
    if (!sh) return [];
    const busy = db.appointments.filter((a) => a.staffId === m.id && a.start.startsWith(d) && a.status !== "canceled" && a.status !== "no_show").map((a) => [minutesOf(a.start.slice(11)), minutesOf(a.start.slice(11)) + a.duration]);
    const earliest = d === todayKey() ? new Date().getHours() * 60 + new Date().getMinutes() + cfg.leadHours * 60 : 0;
    const out: string[] = [];
    for (let tm = minutesOf(sh.from); tm + duration <= minutesOf(sh.to); tm += cfg.slotMin) {
      if (tm < earliest) continue;
      if (busy.some(([a, z]) => tm < z && tm + duration > a)) continue;
      out.push(hhmmOf(tm));
    }
    return out;
  }
  const slotMasters = master ? [master] : candidates;
  const slots = useMemo(() => {
    const set = new Set<string>();
    for (const m of slotMasters) for (const s of slotsFor(m, date)) set.add(s);
    return [...set].sort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [db, date, slotMasters.map((m) => m.id).join(","), duration]);
  const days = Array.from({ length: cfg.maxDays }, (_, i) => addDays(todayKey(), i));

  function go(next: Step) { setStep(next); }
  function nextStep() {
    const seq = firstMaster ? ["master", "services", "time", "contacts", "done"] : ORDER;
    const i = seq.indexOf(step);
    go(seq[Math.min(seq.length - 1, i + 1)] as Step);
  }
  function prevStep() {
    const seq = firstMaster ? ["master", "services", "time", "contacts", "done"] : ORDER;
    const i = seq.indexOf(step);
    go(i <= 0 ? "start" : (seq[i - 1] as Step));
  }
  async function submit() {
    if (!branch || !name.trim() || !phone.trim() || !time) return;
    const chosenMaster = master ?? slotMasters.find((m) => slotsFor(m, date).includes(time)) ?? null;
    let requestId = newId("rq");

    try {
      const timeStart = time.length === 5 ? `${time}:00` : time;
      const res = await fetch("/api/proxy/api/v1/bookings/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: name.trim(),
          client_phone: phone.trim(),
          services: chosen.map((s) => ({ id: s.id, price: String(priceFor(s, chosenMaster)) })),
          date,
          time_start: timeStart,
          total_price: String(total),
          total_duration_min: duration,
          master_id: chosenMaster?.id && chosenMaster.id.includes("-") ? chosenMaster.id : undefined,
          client_comment: comment.trim(),
        }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        if (data?.id) requestId = data.id;
      }
    } catch (e) {
      console.warn("Backend booking submit notice:", e);
    }

    update((d) => ({
      ...d,
      requests: [{
        id: requestId,
        branchId: branch.id,
        clientName: name.trim(),
        phone: phone.trim(),
        serviceId: serviceIds[0] ?? null,
        serviceIds,
        comment: comment.trim(),
        staffId: chosenMaster?.id ?? null,
        wishedAt: `${date}T${time}`,
        source: "online" as const,
        status: "new" as const,
        createdAt: toIsoLocal(new Date()),
      }, ...d.requests],
    }));
    go("done");
  }
  function reset() {
    setStep("start"); setServiceIds([]); setStaffId(null); setTime(null); setName(""); setPhone(""); setComment(""); setFirstMaster(false);
  }

  const canNext = step === "services" ? serviceIds.length > 0 : step === "master" ? true : step === "time" ? !!time : step === "contacts" ? !!name.trim() && !!phone.trim() : true;
  const stepIcon: Record<Exclude<Step, "start">, "scissors" | "badge" | "calendar" | "users" | "sparkles"> = { services: "sparkles", master: "badge", time: "calendar", contacts: "users", done: "sparkles" };
  const seq: Exclude<Step, "start">[] = firstMaster ? ["master", "services", "time", "contacts", "done"] : ["services", "master", "time", "contacts", "done"];

  if (!ready) return <main className="flex min-h-screen items-center justify-center text-sm text-ink-soft">{t.u.common.loading}</main>;

  return (
    <main className="min-h-screen bg-paper px-4 py-8">
      <div className="anim-rise mx-auto w-full max-w-lg overflow-hidden rounded-2xl bg-card shadow-xl">
        <header className="flex items-center gap-3 bg-primary px-5 py-4 text-white">
          <span className="flex size-10 items-center justify-center rounded-xl bg-gold text-primary"><Icon name="calendar" /></span>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold tracking-tight">{cfg.title}</h1>
            <p className="truncate text-xs text-white/70">{branch?.name}{branch?.address ? ` · ${branch.address}` : ""}</p>
          </div>
        </header>

        {!cfg.enabled || !branch ? (
          <p className="px-5 py-10 text-center text-sm text-ink-soft">{b.disabled}</p>
        ) : step === "start" ? (
          <div className="px-5 py-5">
            <p className="text-sm text-ink-soft">{cfg.intro}</p>
            {branches.length > 1 && (
              <label className="mt-4 block text-sm">
                <span className="font-semibold">{b.branch}</span>
                <select value={branch.id} onChange={(e) => setBranchId(e.target.value)} className="mt-1.5 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm">
                  {branches.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                </select>
              </label>
            )}
            <h2 className="mt-5 font-bold">{b.startTitle}</h2>
            <p className="text-xs text-ink-soft">{b.startHint}</p>
            <div className="mt-3 grid gap-3">
              <button type="button" onClick={() => { setFirstMaster(false); go("services"); }} className="press rounded-xl border border-line px-4 py-5 text-center hover:border-primary">
                <span className="mx-auto flex size-10 items-center justify-center rounded-xl bg-gold text-primary"><Icon name="sparkles" /></span>
                <span className="mt-2 block font-semibold">{b.byService}</span>
                <span className="block text-xs text-ink-soft">{b.byServiceHint}</span>
              </button>
              {cfg.chooseMaster && (
                <button type="button" onClick={() => { setFirstMaster(true); go("master"); }} className="press rounded-xl border border-line px-4 py-5 text-center hover:border-primary">
                  <span className="mx-auto flex size-10 items-center justify-center rounded-xl bg-gold text-primary"><Icon name="badge" /></span>
                  <span className="mt-2 block font-semibold">{b.byMaster}</span>
                  <span className="block text-xs text-ink-soft">{b.byMasterHint}</span>
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            <ol className="flex border-b border-line">
              {seq.map((s) => {
                const active = s === step;
                const passed = seq.indexOf(s) < seq.indexOf(step as Exclude<Step, "start">);
                return (
                  <li key={s} className={`flex flex-1 flex-col items-center gap-1 border-b-2 py-2 text-[11px] ${active ? "border-primary text-ink" : passed ? "border-transparent text-primary" : "border-transparent text-ink-soft"}`}>
                    <span className={`flex size-7 items-center justify-center rounded-lg ${active ? "bg-primary text-white" : passed ? "bg-primary/15 text-primary" : "bg-paper"}`}><Icon name={stepIcon[s]} className="size-4" /></span>
                    {b.steps[s]}
                  </li>
                );
              })}
            </ol>

            <div key={step} className="anim-fade-in max-h-[60vh] overflow-y-auto px-5 py-4 [overscroll-behavior:contain]">
              {step === "services" && (
                <>
                  <h2 className="font-bold">{b.pickServices}</h2>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={b.searchServices} className="mt-3 w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-primary" />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" onClick={() => setCat(null)} className={`press rounded-full px-3 py-1 text-xs font-semibold ${!cat ? "bg-primary text-white" : "border border-line"}`}>{b.all}</button>
                    {cats.map((c) => <button key={c.id} type="button" onClick={() => setCat(c.id)} className={`press rounded-full px-3 py-1 text-xs font-semibold ${cat === c.id ? "bg-primary text-white" : "border border-line"}`}>{c.name}</button>)}
                  </div>
                  <ul className="mt-3 space-y-2">
                    {shown.filter((s) => !master || master.serviceIds.includes(s.id)).map((s) => {
                      const on = serviceIds.includes(s.id);
                      return (
                        <li key={s.id}>
                          <button type="button" onClick={() => setServiceIds(on ? serviceIds.filter((x) => x !== s.id) : [...serviceIds, s.id])} className={`press flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left ${on ? "border-primary bg-primary/5" : "border-line"}`}>
                            <span>
                              <span className="block font-semibold">{s.name}</span>
                              <span className="block text-xs text-ink-soft">{s.duration} {b.minutes}{cfg.showPrices ? ` · ${fmtMoney(priceFor(s, master))}` : ""}</span>
                            </span>
                            <span className={`flex size-5 items-center justify-center rounded-md border ${on ? "border-primary bg-primary text-white" : "border-line"}`}>{on && "✓"}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
              {step === "master" && (
                <>
                  <h2 className="font-bold">{b.pickMaster}</h2>
                  <ul className="mt-3 space-y-2">
                    {!firstMaster && (
                      <li>
                        <button type="button" onClick={() => setStaffId(null)} className={`press flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left ${staffId === null ? "border-primary bg-primary/5" : "border-line"}`}>
                          <span className="flex size-10 items-center justify-center rounded-full bg-paper"><Icon name="users" /></span>
                          <span><span className="block font-semibold">{b.anyMaster}</span><span className="block text-xs text-ink-soft">{b.anyMasterHint}</span></span>
                        </button>
                      </li>
                    )}
                    {(firstMaster ? masters : candidates).map((m) => (
                      <li key={m.id}>
                        <button type="button" onClick={() => setStaffId(m.id)} className={`press flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left ${staffId === m.id ? "border-primary bg-primary/5" : "border-line"}`}>
                          <span className="flex size-10 items-center justify-center rounded-full text-sm font-bold text-white" style={{ background: m.color }}>{initials(m.name)}</span>
                          <span><span className="block font-semibold">{m.name}</span><span className="block text-xs text-ink-soft">{db.positions.find((p) => p.id === m.positionId)?.name}</span></span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {step === "time" && (
                <>
                  <h2 className="font-bold">{b.pickTime}</h2>
                  <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                    {days.map((d) => (
                      <button key={d} type="button" onClick={() => { setDate(d); setTime(null); }} className={`press shrink-0 rounded-xl border px-3 py-2 text-center ${date === d ? "border-primary bg-primary text-white" : "border-line"}`}>
                        <span className="block text-[11px] capitalize opacity-80">{fmtDate(d, "ru", { weekday: "short" })}</span>
                        <span className="block text-sm font-bold">{Number(d.slice(8))}</span>
                      </button>
                    ))}
                  </div>
                  {slots.length === 0 ? (
                    <p className="mt-4 rounded-xl border border-dashed border-line px-3 py-6 text-center text-sm text-ink-soft">{b.noSlots}</p>
                  ) : (
                    <div className="mt-4 grid grid-cols-4 gap-2">
                      {slots.map((s) => <button key={s} type="button" onClick={() => setTime(s)} className={`press rounded-lg border py-2 text-sm font-semibold ${time === s ? "border-primary bg-primary text-white" : "border-line hover:border-primary"}`}>{s}</button>)}
                    </div>
                  )}
                </>
              )}
              {step === "contacts" && (
                <>
                  <h2 className="font-bold">{b.contacts}</h2>
                  <div className="mt-3 space-y-3">
                    <label className="block text-sm"><span className="font-semibold">{b.name}</span><input value={name} onChange={(e) => setName(e.target.value)} name="name" autoComplete="name" className="mt-1.5 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-primary" /></label>
                    <label className="block text-sm"><span className="font-semibold">{b.phone}</span><input value={phone} onChange={(e) => setPhone(e.target.value)} name="phone" type="tel" inputMode="tel" autoComplete="tel" placeholder="+996 …" className="mt-1.5 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-primary" /></label>
                    <label className="block text-sm"><span className="font-semibold">{b.comment}</span><input value={comment} onChange={(e) => setComment(e.target.value)} name="comment" className="mt-1.5 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-primary" /></label>
                  </div>
                  <div className="mt-4 rounded-xl bg-paper p-3 text-sm">
                    <div className="font-semibold">{b.summary}</div>
                    <div className="mt-1 text-ink-soft">{chosen.map((s) => s.name).join(", ")} · {duration} {b.minutes}</div>
                    <div className="text-ink-soft">{master?.name ?? b.anyMaster} · {fmtDate(date, "ru", { day: "numeric", month: "long" })} {time}</div>
                    {cfg.showPrices && <div className="mt-1 font-semibold">{b.total}: {fmtMoney(total)}</div>}
                  </div>
                </>
              )}
              {step === "done" && (
                <div className="anim-pop py-6 text-center">
                  <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary/15 text-primary"><Icon name="sparkles" className="size-7" /></span>
                  <h2 className="mt-3 text-lg font-bold">{b.doneTitle}</h2>
                  <p className="mt-1 text-sm text-ink-soft">{b.doneHint}</p>
                  <p className="mt-3 text-sm">{chosen.map((s) => s.name).join(", ")} · {fmtDate(date, "ru", { day: "numeric", month: "long" })} {time}</p>
                  <button type="button" onClick={reset} className="press mt-5 h-11 rounded-xl border-[1.5px] border-line-strong px-4 text-sm font-bold text-ink-mid">{b.again}</button>
                </div>
              )}
            </div>

            {step !== "done" && (
              <footer className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
                <button type="button" onClick={prevStep} className="press h-11 rounded-xl border-[1.5px] border-line-strong px-4 text-sm font-bold text-ink-mid">‹ {b.back}</button>
                {step === "contacts" ? (
                  <button type="button" onClick={submit} disabled={!canNext} className="press h-11 rounded-xl bg-gold px-5 text-sm font-extrabold text-primary disabled:opacity-50">{b.submit}</button>
                ) : (
                  <button type="button" onClick={nextStep} disabled={!canNext} className="press h-11 rounded-xl bg-gold px-5 text-sm font-extrabold text-primary disabled:opacity-50">{b.next} ›</button>
                )}
              </footer>
            )}
          </>
        )}
      </div>
      <p className="mt-4 text-center text-xs text-ink-soft">{t.appName}</p>
    </main>
  );
}
